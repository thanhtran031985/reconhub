# Hướng dẫn triển khai ReconHub trên Windows Server

Tài liệu hướng dẫn cài đặt và vận hành ReconHub trên môi trường máy chủ Windows (Windows Server 2019/2022 hoặc Windows 10/11) chạy trực tiếp Python với **Waitress** và **Windows Services** (qua NSSM).

---

## 1. Yêu cầu hệ thống
- Hệ điều hành: Windows Server 2019/2022 hoặc Windows 10/11 Pro/Enterprise 64-bit.
- Python: 3.12 (khuyến nghị cài đặt qua công cụ quản lý gói `uv` hoặc từ python.org).
- Bộ quản lý gói: `uv` (tải từ https://docs.astral.sh/uv/).
- Quản lý Windows Service: `nssm.exe` (bản win64, tải từ https://nssm.cc/download).
- Kết nối mạng: VPN tới Oracle Database Server (nếu sử dụng nguồn Oracle).
- Dung lượng đĩa: Tối thiểu 20 GB trống cho dữ liệu tạm và bản sao lưu.

---

## 2. Các bước cài đặt ban đầu

### Bước 2.1: Chuẩn bị mã nguồn và môi trường Python
Mở **PowerShell (Run as Administrator)**:

```powershell
# Di chuyển tới thư mục cài đặt (ví dụ: D:\reconhub)
cd D:\reconhub

# Đồng bộ thư viện bao gồm gói phục vụ sản xuất (waitress)
uv sync --extra prod

# Tạo file cấu hình môi trường .env từ mẫu .env.example
Copy-Item .env.example .env
# Chỉnh sửa file .env: FLASK_SECRET_KEY, RECON_SECRET_KEY, RECON_DB_URL, v.v.
notepad .env

# Chạy migration cơ sở dữ liệu
uv run poe db-migrate

# Khởi tạo tài khoản quản trị ban đầu
uv run python -m app.cli create-admin --username admin --password "MatKhauManh123" --fullname "Quản Trị Viên"
```

### Bước 2.2: Tải công cụ NSSM
1. Tải bản nssm từ https://nssm.cc/download.
2. Giải nén và sao chép file `nssm.exe` (từ thư mục `win64`) vào `D:\reconhub\deploy\windows\nssm.exe` (hoặc đặt vào `C:\Windows\System32`).

### Bước 2.3: Đăng ký Windows Services
Chạy script cài đặt tự động với quyền Administrator:

```powershell
cd D:\reconhub\deploy\windows
.\install-services.ps1 -Port 8050 -Threads 4
```

Script sẽ tự động:
1. Đăng ký service `ReconHub-Web`: Chạy web application trên cổng 8050 qua Waitress.
2. Đăng ký service `ReconHub-Worker`: Chạy tiến trình nền xử lý hàng đợi đối soát.
3. Cấu hình tự khởi động cùng Windows (Automatic).
4. Cấu hình tự động khởi động lại sau 5 giây nếu gặp sự cố.
5. Cấu hình xoay vòng file log (mỗi file tối đa 10 MB) tại thư mục `logs/`.
6. Khởi động cả 2 dịch vụ.

### Bước 2.4: Đăng ký tác vụ sao lưu tự động hàng ngày
```powershell
cd D:\reconhub\deploy\windows
.\backup-task.ps1 -Time "01:00"
```
Tác vụ sao lưu sẽ tự động chạy hàng ngày lúc 01:00 AM qua Windows Task Scheduler, gọi lệnh `app.cli backup` và tự động giữ lại 14 bản sao lưu gần nhất tại `data/backup/` hoặc `backup/`.

---

## 3. Quản lý và giám sát dịch vụ

### Kiểm tra trạng thái dịch vụ
```powershell
Get-Service ReconHub-Web, ReconHub-Worker
```

### Khởi động / Dừng / Khởi động lại dịch vụ
```powershell
# Khởi động
Start-Service ReconHub-Web
Start-Service ReconHub-Worker

# Dừng
Stop-Service ReconHub-Web
Stop-Service ReconHub-Worker

# Khởi động lại
Restart-Service ReconHub-Web
Restart-Service ReconHub-Worker
```

### Xem file log
- Web access & stdout: `logs\web.log`
- Web error log: `logs\web_error.log`
- Worker log: `logs\worker.log`
- Worker error log: `logs\worker_error.log`

Xem log thời gian thực:
```powershell
Get-Content -Path D:\reconhub\logs\web.log -Wait -Tail 50
Get-Content -Path D:\reconhub\logs\worker.log -Wait -Tail 50
```

### Gỡ bỏ dịch vụ (khi cần chuyển máy chủ)
```powershell
cd D:\reconhub\deploy\windows
.\uninstall-services.ps1
```

