# 100-multi-profile-run — Cho phép chọn nhiều Profile khi chạy đối soát và hỗ trợ hiển thị lịch sử

- Ngày tạo: 2026-11-20
- Giai đoạn: GĐ3
- Phụ thuộc: 10, 12
- Nhánh git: feat/100-multi-profile-run

## Mục tiêu
Cho phép người dùng chọn một hoặc nhiều (Multi) Profile khi thực hiện chạy đối soát trên trang `/runs/new` thay vì chỉ chọn 1 profile duy nhất. Khi chạy nhiều profile, hệ thống tự động khởi tạo N lần chạy (`RECON_RUN`) tương ứng, dùng chung file Excel tạm đã parse để tối ưu hiệu năng, đồng thời xem trước được câu lệnh SQL của từng Profile qua giao diện dạng Tab. Trang Lịch sử (`/history`) bổ sung bộ lọc Profile và hiển thị trực quan các lượt chạy.

## Phạm vi
- **Service (`app/services/run_service.py` & `app/schemas/run.py`)**:
  - Bổ sung schema `CreateMultiRunParams` (hỗ trợ `profile_codes: list[str]`) hoặc mở rộng logic tạo hàng loạt run.
  - Bổ sung service `create_multi_run` hoặc mở rộng `create_run` cho phép nhận danh sách profile codes, sinh ra các bản ghi `RECON_RUN` độc lập trong cùng 1 đợt submit, ghi audit log tương ứng.
- **UI `/runs/new` (`app/ui/pages/new_run.py`)**:
  - Chuyển đổi component chọn Profile từ `dmc.Select` sang `dmc.MultiSelect` (kèm tiện ích chọn tất cả hoặc chọn mặc định).
  - Chuyển đổi Card 3 "Câu lệnh SQL đối soát DB" thành giao diện `dmc.Tabs` để xem trước SQL tương ứng với từng profile đã được chọn.
  - Xử lý callback Submit:
    - Nếu chọn đúng 1 profile: chuyển hướng trực tiếp đến `/runs/<id>` như cũ.
    - Nếu chọn nhiều profile: chuyển hướng về trang `/history` kèm thông báo thành công tổng số run đã đưa vào hàng đợi.
- **UI `/history` (`app/ui/pages/history.py`)**:
  - Thêm dropdown bộ lọc `Profile` trên thanh Filter bar, tự động cập nhật danh sách profile khi người dùng chọn Template cụ thể.
  - Giữ nguyên cột Profile đã có, hiển thị thông tin rõ ràng.
- **Kiểm thử**:
  - Unit test cho service tạo multi-run.
  - Test kiểm tra preview SQL nhiều tabs và logic submit nhiều profile.
  - Test bộ lọc profile trên trang lịch sử.

## Ngoài phạm vi
- Không thay đổi bảng `RECON_RUN` thành 1 run chứa nhiều profile (vì phá vỡ cấu trúc bảng kết quả `RECON_RESULT_ROW` và `RECON_RUN_SUMMARY`).
- Không sửa đổi trang kết quả đơn lẻ `/runs/<id>`.

## Thiết kế
- `designs/components/Screen03_NewRun.md`
- `designs/components/Screen07_History.md`

## Spec liên quan
- `docs/specs/02_database_schema.md`
- `docs/specs/03_template_config.md`
- `docs/specs/04_recon_engine.md`

## Quyết định kiến trúc
- **Kiến trúc N-runs**: Khi submit $K$ profile, sinh ra $K$ bản ghi `RECON_RUN` độc lập.
- **Tối ưu file tạm**: Cả $K$ runs cùng dùng chung `FILE_ID` và `EXCEL_LOAD_ID`, chỉ đọc và chuẩn hóa file 1 lần, các worker lấy chung dữ liệu tạm và chỉ tính toán aggregate/query DB riêng theo từng profile.

## Các bước
### Bước 1 — Service: Mở rộng `CreateRunParams` và hàm `create_multi_run`
- Làm: Thêm `CreateMultiRunParams` trong `app/schemas/run.py` và service `create_multi_run` trong `app/services/run_service.py`.
- Test viết trước: `tests/unit/test_multi_profile_run.py`.
- Kiểm tra: `uv run pytest tests/unit/test_multi_profile_run.py` → PASSED.

### Bước 2 — UI `/runs/new`: MultiSelect Profile và Tabs SQL Preview
- Làm: Cập nhật `app/ui/pages/new_run.py`:
  - Đổi `new-run-profile-select` sang `dmc.MultiSelect`.
  - Cập nhật Card 3 thành `dmc.Tabs` xem SQL theo từng profile đã chọn.
  - Cập nhật callback submit xử lý `list[str]` profile_codes.
- Test: Viết test cho render và callback UI.
- Kiểm tra: `uv run pytest tests/unit/test_new_run_multi_profile.py` → PASSED.

### Bước 3 — UI `/history`: Bổ sung bộ lọc Profile
- Làm: Cập nhật `app/ui/pages/history.py` thêm bộ lọc Profile và callback cập nhật options profile theo template đã chọn.
- Test: Viết test kiểm tra filter profile.
- Kiểm tra: `uv run pytest tests/unit/test_history_profile_filter.py` → PASSED.

### Bước 4 — Rà soát toàn bộ, kiểm thử chất lượng và đóng task
- Làm: Chạy `typecheck`, `lint`, `test`, `security-check`.
- Kiểm tra: Toàn bộ kiểm thử xanh, cập nhật dashboard.

## Chấp nhận khi
- [ ] Chọn được 1 hoặc nhiều profile trên `/runs/new`.
- [ ] Xem trước được SQL của từng profile qua Tabs.
- [ ] Bấm chạy tạo đủ N runs độc lập trong DB, đưa vào hàng đợi.
- [ ] Trang `/history` lọc được theo profile và hiển thị đúng thông tin.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh.

### Data Model Impact
- [x] Task không thay đổi database schema (tái sử dụng 100% bảng `RECON_RUN` hiện tại).

## Câu hỏi mở
- Không.
