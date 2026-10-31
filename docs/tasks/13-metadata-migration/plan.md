# Kế hoạch thực hiện — 13-metadata-migration

## Mục tiêu
Cung cấp giải pháp toàn diện cho Quản trị viên (Admin) chuyển dữ liệu `RECON_APP` từ SQLite sang Oracle: kiểm tra trước (precheck), bật chế độ bảo trì, chép dữ liệu giữ nguyên ID theo lô 5.000, đồng bộ identity Oracle, đối chiếu số dòng và checksum, hướng dẫn đổi `RECON_DB_URL`, và xóa an toàn bản lưu SQLite cũ khi đã chạy trên Oracle.

---

## Các bước triển khai

### Bước 1 — Precheck + Chế độ bảo trì
- **Tạo `app/services/metadata_migration.py`:**
  - `precheck(ctx: Ctx, target_ds_id: int, mode: str = "NO_TEMP") -> dict[str, Any]`:
    - Kiểm tra quyền Admin.
    - Kiểm tra đích Oracle đã đăng ký (mục đích `METADATA` hoặc `TARGET`).
    - Kiểm tra kết nối Oracle và phiên bản >= 19.
    - Kiểm tra schema đích: nếu đã có bảng `RECON_*` có dữ liệu thì báo lỗi `MIGRATION_TARGET_NOT_EMPTY`.
    - Kiểm tra hàng đợi: không có run nào đang `QUEUED` hoặc `RUNNING` (nếu có báo lỗi `MIGRATION_RUNNING`).
    - Thống kê ước lượng số dòng và dung lượng các bảng cần chuyển.
  - `set_maintenance_mode(ctx: Ctx, enabled: bool) -> bool`:
    - Ghi nhận `RECON_APP_SETTING.MAINTENANCE = 'Y'/'N'`.
- **Test:** Viết unit tests kiểm tra các trường hợp precheck (đích có dữ liệu, run đang chạy, thành công).

### Bước 2 — Chép dữ liệu + Đồng bộ Identity Oracle
- **Tạo hàm `start_migration(ctx: Ctx, target_ds_id: int, mode: str = "NO_TEMP")`:**
  - Tự động gọi `precheck`.
  - Kích hoạt chế độ bảo trì.
  - Tạo bảng trên đích Oracle (`metadata.create_all(target_engine)`).
  - Chép dữ liệu từng bảng theo thứ tự khóa ngoại (21 bảng) theo lô 5.000 dòng:
    - `NO_TEMP`: Bỏ qua `RECON_EXCEL_LOAD` và `RECON_EXCEL_ROW`.
    - `FULL`: Chép toàn bộ bảng.
    - `CONFIG_ONLY`: Chỉ chép các bảng cấu hình (User, Template, DataSource, Setting, IssueReason).
  - Đồng bộ identity Oracle: `SELECT MAX(ID) FROM <TABLE>` -> `ALTER TABLE <TABLE> MODIFY ID GENERATED AS IDENTITY (START WITH <max_id + 1>)`.
  - Đối chiếu số dòng từng bảng và tính checksum SHA256 các khóa chính của 3 bảng lớn nhất.
  - Cập nhật bản ghi `RECON_METADATA_MIGRATION` (`STATUS='DONE'`).
  - Trả về báo cáo đối chiếu và hướng dẫn đổi `RECON_DB_URL`.
- **Test:** Viết unit test chép dữ liệu sang SQLite đích giả lập và kiểm tra tính toàn vẹn.

### Bước 3 — Kiểm tra + Lỗi giữa chừng (Khả năng chịu lỗi)
- Xử lý ngắt kết nối hoặc ngoại lệ trong quá trình chép:
  - SQLite nguồn hoàn toàn nguyên vẹn, không bị chỉnh sửa.
  - Bản ghi migration ở trạng thái `FAILED` kèm `ERROR_MSG`.
- Hàm `clean_target_schema(ctx: Ctx, target_ds_id: int, confirm_schema: str)`:
  - Cho phép Admin xóa/truncate các bảng `RECON_*` ở đích sau khi migration bị lỗi để chạy lại (yêu cầu gõ đúng tên schema để xác nhận).
- **Test:** Giả lập lỗi ngắt kết nối giữa chừng, kiểm tra SQLite nguồn không đổi và đích được dọn dẹp an toàn.

### Bước 4 — Chạy trên Oracle + Xóa bản lưu SQLite cũ
- Hàm `delete_old_sqlite(ctx: Ctx, confirm_filename: str) -> dict[str, Any]`:
  - Chỉ cho phép thực hiện khi ứng dụng đang chạy trên Oracle (`engine.dialect.name == "oracle"`).
  - Yêu cầu nhập đúng tên file lưu trong `OLD_SQLITE_PATH`.
  - Xóa file trên đĩa cứng, ghi `RECON_PURGE_LOG` (scope `OLD_SQLITE`) và audit log.
- Cập nhật tài liệu `docs/OPERATIONS.md` mục Đổi DB RECON_APP.
- **Test:** Viết unit test kiểm tra ràng buộc chỉ xóa khi chạy Oracle và xác thực tên file.

### Bước 5 — Giao diện UI + CLI
- **Giao diện trong `app/ui/pages/data_sources.py` (Tab Lưu trữ RECON_APP):**
  - Khối "Chuyển dữ liệu sang Oracle": Chọn đích Oracle, chọn phạm vi (`NO_TEMP`, `FULL`, `CONFIG_ONLY`), nút Kiểm tra trước, nút Chuyển dữ liệu.
  - Hộp thoại Xóa bảng RECON_* ở đích khi có lỗi dở dang (gõ tên schema).
  - Khối "Bản lưu SQLite cũ": Hiển thị đường dẫn, dung lượng, ngày chuyển; nút Xóa bản lưu SQLite cũ kèm modal gõ tên file.
- **CLI `app/cli.py`:**
  - Hoàn thiện lệnh `migrate-metadata`: `uv run python -m app.cli migrate-metadata --target <id> --mode NO_TEMP`.
- **Test:** Chạy toàn bộ test suite, lint, typecheck và E2E.
