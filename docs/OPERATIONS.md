# ReconHub — Hướng dẫn vận hành hệ thống (Operations Guide)

Tài liệu này hướng dẫn quản trị viên và đội ngũ vận hành hệ thống ReconHub trong các hoạt động quản trị, bảo trì và chuyển đổi cơ sở dữ liệu.

---

## 1. Đổi DB RECON_APP (Chuyển từ SQLite sang Oracle)

ReconHub hỗ trợ chuyển toàn bộ metadata, cấu hình template, lịch sử chạy và dữ liệu đối soát từ SQLite nội bộ sang hệ quản trị cơ sở dữ liệu Oracle thông qua công cụ tự động.

### 1.1 Điều kiện tiên quyết
1. Đã đăng ký Data Source Oracle đích trong màn hình **Data Sources** với cờ hoạt động (`IS_ACTIVE = Y`).
2. Schema đích trên Oracle phải là schema mới hoặc schema trống (không chứa các bảng `RECON_*` có dữ liệu). Nếu có bảng cũ từ lần chuyển thử nghiệm trước, sử dụng chức năng **Xóa schema đích** để dọn dẹp.
3. Không có run nào đang ở trạng thái chờ (`QUEUED`) hoặc đang xử lý (`PROCESSING` / `RUNNING`).

### 1.2 Các bước thực hiện
Hệ thống hỗ trợ 2 cách chuyển:

#### Cách 1: Qua giao diện Web (Khuyên dùng)
1. Đăng nhập với vai trò **Quản trị viên (Admin)**.
2. Vào màn hình **Data Sources** > chọn tab **Lưu trữ RECON_APP**.
3. Tại khối **Chuyển dữ liệu sang Oracle**:
   - Chọn Data Source Oracle đích.
   - Chọn chế độ chuyển:
     - `NO_TEMP` *(Mặc định)*: Chuyển toàn bộ cấu hình, lịch sử và kết quả đối soát; bỏ qua dữ liệu Excel tạm.
     - `FULL`: Chuyển tất cả bao gồm cả dữ liệu dòng Excel tạm.
     - `CONFIG_ONLY`: Chỉ chuyển cấu hình (user, template, data source), không chuyển lịch sử chạy.
   - Nhấn nút **Kiểm tra trước (Precheck)** để hệ thống xác thực tính sẵn sàng và tính toán dung lượng ước tính.
   - Nhấn **Chuyển sang Oracle**. Hệ thống sẽ tự động bật chế độ bảo trì, khởi tạo schema trên Oracle, sao chép dữ liệu theo lô 5.000 dòng, đồng bộ sequence/identity và đối chiếu số dòng + SHA256 checksum.

#### Cách 2: Qua dòng lệnh CLI
Chạy lệnh quản trị:
```bash
# Xem trước điều kiện (Dry-run)
uv run python -m app.cli migrate-metadata --target-ds <ID_ORACLE> --mode NO_TEMP --dry-run

# Thực hiện chuyển dữ liệu thật
uv run python -m app.cli migrate-metadata --target-ds <ID_ORACLE> --mode NO_TEMP
```

### 1.3 Cập nhật biến môi trường và khởi động lại
Sau khi phiên chuyển báo cáo trạng thái `DONE`:
1. Dừng ứng dụng web ReconHub và background worker.
2. Mở file `.env` trên máy chủ và cập nhật chuỗi kết nối:
   ```env
   RECON_DB_URL=oracle+oracledb://<USERNAME>:<PASSWORD>@<HOST>:<PORT>/?service_name=<SERVICE_NAME>
   ```
3. Chạy lệnh kiểm tra schema:
   ```bash
   uv run poe db-migrate
   ```
4. Khởi động lại dịch vụ web và worker.

### 1.4 Quản lý bản lưu SQLite cũ
- Sau khi chuyển đổi thành công, file SQLite gốc (ví dụ `data/recon_app.db`) được giữ nguyên làm bản lưu dự phòng an toàn.
- Hệ thống **tuyệt đối không tự ý xóa** file SQLite cũ.
- Khi hệ thống đã vận hành ổn định trên Oracle và Admin muốn giải phóng dung lượng đĩa:
  - Truy cập tab **Lưu trữ RECON_APP** trên giao diện Web (chỉ kích hoạt khi ứng dụng đang kết nối Oracle).
  - Tại khối **Bản lưu SQLite cũ**, nhấn **Xóa bản lưu**.
  - Nhập chính xác tên file xác nhận (ví dụ `recon_app.db`) để xóa file vật lý và ghi nhật ký kiểm toán (`RECON_PURGE_LOG`, `RECON_AUDIT_LOG`).

