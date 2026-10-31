# 13-metadata-migration — Chuyển RECON_APP từ SQLite sang Oracle, xóa bản lưu SQLite cũ

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ3
- Phụ thuộc: 02, 12
- Nhánh git: feat/13-metadata-migration

## Mục tiêu
Admin chọn đích Oracle đã đăng ký, kiểm tra trước, chuyển dữ liệu (mặc định không gồm dữ liệu tạm) với tiến độ theo bảng và đối chiếu; đổi RECON_DB_URL để chạy trên Oracle; file SQLite cũ giữ lại và chỉ xóa khi Admin yêu cầu.

## Phạm vi
- services/metadata_migration.py (spec 08): precheck, start (job trong worker), status, list, xóa bảng RECON_* ở đích (gõ tên schema), delete_old_sqlite (gõ tên file, chỉ khi đang chạy trên Oracle)
- Đồng bộ identity Oracle sau khi chép; chế độ bảo trì
- UI: khối Chuyển dữ liệu và khối Bản lưu SQLite cũ trong tab Lưu trữ
- CLI migrate-metadata; docs/OPERATIONS.md mục Đổi DB RECON_APP

## Ngoài phạm vi
- Oracle → SQLite
- Đổi DB không khởi động lại

## Thiết kế
- designs/components/Screen08-DataSources (khối Chuyển dữ liệu, Bản lưu SQLite cũ)

## Spec liên quan
- docs/specs/08_metadata_migration.md
- docs/PRD.md C8, C10

## Quyết định kiến trúc
- Giữ nguyên ID; SQLite nguồn không bị sửa ngoài cờ bảo trì

## Các bước
### Bước 1 — Precheck + bảo trì
- Làm: Precheck + bảo trì
- Test viết trước: đích có dữ liệu → MIGRATION_TARGET_NOT_EMPTY; run đang chạy → MIGRATION_RUNNING (unit với đích giả)
- Kiểm tra: `uv run poe test`

### Bước 2 — Chép + identity
- Làm: Chép + identity
- Test viết trước: oracle (RECON_APP_TEST): seed SQLite 2 run G01 → NO_TEMP và FULL → số dòng khớp; JSON, Decimal, thời gian giữ nguyên
- Kiểm tra: `uv run poe test-oracle` (VPN; người dùng chạy và dán kết quả)

### Bước 3 — Kiểm tra + lỗi giữa chừng
- Làm: Kiểm tra + lỗi giữa chừng
- Test viết trước: ngắt kết nối giả ở RECON_RESULT_ROW → FAILED, SQLite không đổi
- Kiểm tra: `uv run poe test`; `uv run poe test-oracle` (VPN; người dùng chạy và dán kết quả)

### Bước 4 — Chạy trên Oracle + bản lưu cũ
- Làm: Chạy trên Oracle + bản lưu cũ
- Test viết trước: oracle: đăng nhập bằng user cũ, mở run cũ, tạo run mới không trùng ID; xóa file SQLite cũ chỉ khi đang chạy Oracle, ghi purge log
- Kiểm tra: `uv run poe test-oracle` (VPN; người dùng chạy và dán kết quả)

### Bước 5 — UI + CLI
- Làm: UI + CLI
- Test viết trước: e2e khối chuyển (đích giả), khối bản lưu cũ
- Kiểm tra: `uv run poe e2e`

## Chấp nhận khi
- [ ] Chuyển được sang RECON_APP_TEST và chạy tiếp trên Oracle
- [ ] Lỗi giữa chừng không hỏng SQLite
- [ ] File SQLite cũ chỉ xóa khi Admin yêu cầu
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- —
