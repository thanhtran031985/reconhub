# Spec 07 – Chiến lược kiểm thử

## 1. Tầng test

| Tầng | Công cụ | Phạm vi | Lệnh |
|---|---|---|---|
| Unit engine | pytest | Hàm engine, sql_guard, sql_builder | `uv run poe test-engine` |
| Golden | pytest | Pipeline đầy đủ, phía DB là `db.parquet` (không cần Oracle) | `uv run poe test-engine` |
| Integration SQLite | pytest + file SQLite tạm | repo, service, worker, Alembic, auth, xóa dữ liệu tạm | `uv run poe test` |
| Integration Oracle | pytest, marker `oracle` | fetch/catalog trên bảng test do người dùng tạo; Alembic + chuyển metadata trên schema `RECON_APP_TEST` | `uv run poe test-oracle` (cần VPN + `ORACLE_TEST_*`; thiếu biến → skip) |
| Service | pytest | Quyền, mã lỗi, ServiceResult | `uv run poe test` |
| UI unit | pytest | Hàm dựng component, build_column_defs, formatter | `uv run poe test` |
| E2E | pytest-playwright, Dash thật, SQLite tạm, service nguồn giả | Luồng chính | `uv run poe e2e` |

- `uv run poe test` không cần VPN: test Oracle tự skip, báo số test skip.
- Test Oracle chỉ **đọc** bảng nguồn test; riêng test chuyển metadata được tạo/xóa bảng RECON_* trong `ORACLE_TEST_APP_USER` (dọn sạch trước và sau).
- Mục tiêu: engine ≥ 90% dòng; mọi mã lỗi có ít nhất một test.

## 2. Golden case
`tests/golden/<case>/`: `input.xlsx` (hoặc tham chiếu samples), `template.json`, `db.parquet`, `params.json`, `expected.json`. Cập nhật bằng `uv run poe golden-update CASE=…` và giải thích ở decisions.md.

| Case | Kiểm tra |
|---|---|
| G01_dtp_by_invoice | Sample 190 hóa đơn, BY_INVOICE; DB giả lập đúng như `scripts/oracle/02_seed_src_test.sql`: 3 HĐ lệch tiền (C26TBD0031338, C26TBD0031375, C26TBD0031412), 1 HĐ lệch ngày (C26TBD0031350), 2 HĐ thiếu trong DB (C26TBD0031435, C26TBD0031485), 2 HĐ thiếu trong Excel (C26TBD0099901, C26TBD0099902) → Khớp 184, Lệch 4, Thiếu DB 2, Thiếu Excel 2 |
| G02_dtp_by_day_point | Cùng dữ liệu, BY_DAY_POINT |
| G03_leading_zero | "0334", "0304422444-021" giữ số 0 |
| G04_excel_serial_date | Ngày serial và chuỗi lẫn nhau |
| G05_footer_total | Dòng tổng bị loại; control total 366.732.000 khớp và trường hợp không khớp |
| G06_time_range | p_from/p_to cắt dòng Excel, đếm out_of_range; tắt apply_range_excel → MISSING_IN_DB |
| G07_inconsistent | Một HĐ 2 ngày → INCONSISTENT |
| G08_duplicate | aggregate=false, khóa lặp → DUPLICATE |
| G09_invalid | Tiền "abc", ngày sai, khóa trống → INVALID kèm số dòng |
| G10_tolerance | abs_tol, pct_tol, round, null_as |
| G11_value_map_filter | value_map STATUS + profile filter hai phía |
| G12_csv | CSV `;`, UTF-8-SIG |
| G13_purge | Chạy G01 → mark_checked(purge) → row_detail trả purged, export đúng số; 2 run dùng chung EXCEL_LOAD chỉ xóa khi cả hai được yêu cầu |

Test riêng SQLite: 2 worker (2 process) lấy job không trùng; lưu nháp template khi worker đang ghi 200.000 dòng không lỗi `database is locked`; Decimal `0.1+0.2` lưu/đọc chính xác.
Test auth: sai 5 lần khóa 15 phút; đổi mật khẩu vô hiệu phiên cũ; MUST_CHANGE_PW chặn mọi page; LAST_ADMIN; thông báo lỗi không lộ user tồn tại.

## 3. Dữ liệu seed (`uv run poe db-seed`, SQLite)
4 người dùng mẫu (admin, owner, operator, viewer; mật khẩu `123` chỉ ở APP_ENV=dev/test, MUST_CHANGE_PW=N), Data Source `ORACLE_TEST` (nếu có biến ORACLE_TEST_*), template DTP (DRAFT).

## 4. E2E (đăng nhập bằng user seed; phía nguồn dùng fetcher giả trả `db.parquet` của G01)
1. Đăng nhập sai 5 lần → thông báo khóa; Admin mở khóa ở màn Người dùng; Admin tạo user mới, user đăng nhập lần đầu buộc đổi mật khẩu.
2. Admin tạo Data Source, Kiểm tra kết nối (fetcher giả), tab Lưu trữ thấy SQLite "Đang dùng" và khối Dữ liệu tạm.
3. Template Owner đăng ký template từ sample: bước 3 chọn bảng RECON_SRC.SRC_FACT_INVOICE_DTP, INVOICE_DATE cho Từ/Đến, ORG_CODE cho Đơn vị; dry-run; kích hoạt.
4. Operator upload, nhập 01/02/2026 00:00:00 – 05/02/2026 23:59:59, chạy, thấy số như G01, mở chi tiết dòng lệch, export.
5. Viewer không thấy menu Chạy đối soát; gọi service run.create với ctx Viewer → FORBIDDEN.
6. Operator bấm "Đã kiểm tra xong" → chi tiết hiện "Dữ liệu Excel gốc đã xóa lúc …", export vẫn tải được.
7. Admin xóa theo điều kiện ở tab Lưu trữ: xem trước số run/dung lượng, gõ XOA, nhật ký xóa có dòng mới.
8. Mỗi màn chính chụp 4 trạng thái.

Kiểm tay qua VPN (ghi vào progress.md): chạy run thật trên `ORACLE_TEST` cho số như G01; chuyển metadata sang `RECON_APP_TEST`.

## 5. Hiệu năng (task 16)
1.000.000 dòng tổng hợp: run ≤ 120 giây (không tính thời gian truyền qua VPN), RAM worker ≤ 6GB. Grid trang 200 dòng ≤ 500 ms.
