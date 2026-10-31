# Kế hoạch — 16-production-readiness

## Mục tiêu
Triển khai sản xuất trên Windows (waitress + Windows Service) và Linux (gunicorn + systemd), cơ chế sao lưu SQLite tự động giữ 14 bản, log xoay vòng, benchmark 1 triệu dòng ≤ 120s, và tài liệu vận hành toàn diện `docs/OPERATIONS.md`.

## Các bước triển khai

### Bước 1 — Windows
1. Tạo `app/wsgi.py` nạp Flask server từ `create_app().server`.
2. Khai báo optional dependency `prod` trong `pyproject.toml` (`waitress>=3.0.0` và `gunicorn>=23.0.0; sys_platform != 'win32'`).
3. Tạo thư mục `deploy/windows/`:
   - `install-services.ps1`: Tự động đăng ký 2 dịch vụ Windows: `ReconHub-Web` (waitress) và `ReconHub-Worker` (worker).
   - `uninstall-services.ps1`: Gỡ bỏ dịch vụ.
   - `start-services.ps1`, `stop-services.ps1`: Quản lý dịch vụ.
   - `backup-task.ps1`: Script PowerShell đăng ký Task Scheduler chạy backup hàng ngày lúc 01:00 AM.
   - `README.md`: Hướng dẫn cài đặt, cấu hình tài khoản dịch vụ và thiết lập trên Windows Server.
4. Kiểm tra wsgi app khởi động thành công với waitress.

### Bước 2 — Linux
1. Tạo thư mục `deploy/linux/`:
   - `reconhub-web.service`: systemd unit cho web server gunicorn.
   - `reconhub-worker.service`: systemd unit cho worker xử lý hàng đợi.
   - `reconhub-backup.service` và `reconhub-backup.timer`: systemd timer chạy backup lúc 01:00 AM.
   - `nginx.conf`: File cấu hình Nginx reverse proxy mẫu (caching, proxy headers, timeout 600s, max body size 100M).
   - `install.sh`: Script bash tự động cài đặt, tạo user hệ thống `reconhub`, copy systemd units và kích hoạt.
   - `README.md`: Hướng dẫn triển khai chi tiết cho Ubuntu/Debian và RHEL/CentOS.

### Bước 3 — Backup CLI & Logging
1. Bổ sung lệnh `backup` trong `app/cli.py`:
   - Thực hiện `VACUUM INTO` trên SQLite, lưu vào `backup/recon_app_YYYYMMDD_HHMMSS.db`.
   - Cơ chế tự động dọn dẹp, giữ lại tối đa 14 bản sao lưu gần nhất.
   - Bổ sung lệnh `restore` khôi phục an toàn database từ bản lưu.
2. Cấu hình xoay vòng log (RotatingFileHandler / structlog) vào thư mục `logs/`.
3. Viết unit test trong `tests/unit/test_cli_backup.py` kiểm tra:
   - Tạo bản backup hợp lệ, mở và đọc được dữ liệu.
   - Tự động xoay vòng giữ đúng 14 bản sao lưu.

### Bước 4 — Benchmark 1 triệu dòng
1. Viết bài test benchmark `tests/bench/test_bench_one_million.py`:
   - Sinh dữ liệu 1.000.000 dòng tổng hợp bằng Polars.
   - Đo thời gian đọc, chuẩn hóa, group by và so sánh kết quả.
   - Xác nhận thời gian hoàn thành ≤ 120 giây (spec 07 mục 5).
2. Ghi kết quả đo đạc chi tiết vào `docs/tasks/16-production-readiness/progress.md`.

### Bước 5 — Tài liệu vận hành (OPERATIONS.md)
1. Cập nhật và hoàn thiện `docs/OPERATIONS.md`:
   - Hướng dẫn cài đặt mới (Windows Server & Linux Server).
   - Quy trình nâng cấp chuẩn 5 bước: Dừng service -> git pull -> uv sync --frozen -> uv run poe db-migrate -> Chạy lại service.
   - Quy trình sao lưu và khôi phục database (SQLite & Oracle).
   - Quy trình xử lý sự cố: worker treo, restart stale jobs, hết dung lượng đĩa.
   - Hướng dẫn xoay mã bí mật `RECON_SECRET_KEY`, `FLASK_SECRET_KEY`.
   - Hướng dẫn đổi DB RECON_APP từ SQLite sang Oracle (`migrate-metadata`).
   - Hướng dẫn dọn dẹp dữ liệu tạm định kỳ thủ công (`purge-temp`).

## Tiêu chí nghiệm thu
- `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`, `uv run poe e2e` xanh 100%.
- Benchmark 1.000.000 dòng đạt ≤ 120s.
- Toàn bộ 17/17 tasks trên dashboard hoàn tất.
