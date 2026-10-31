# Tiến độ — 16-production-readiness

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Windows | ✅ | 2026-11-01 | |
| 2 | Linux | ✅ | 2026-11-01 | |
| 3 | Backup + log | ✅ | 2026-11-01 | |
| 4 | Bench | ✅ | 2026-11-01 | |
| 5 | Tài liệu vận hành | ✅ | 2026-11-01 | |

## Nhật ký
### Bước 1 — 2026-11-01
- Lập kế hoạch chi tiết vào `plan.md`.
- Tạo nhánh `feat/16-production-readiness`.
- Khai báo optional dependency `prod` (`waitress>=3.0.0`, `gunicorn>=23.0.0; sys_platform != 'win32'`) trong `pyproject.toml` và đồng bộ qua `uv sync --extra prod`.
- Hoàn thiện `app/wsgi.py` nạp Flask server từ `create_app().server`.
- Xây dựng bộ script Windows deployment tại `deploy/windows/`:
  - `install-services.ps1`: Tự động đăng ký 2 Windows Services (`ReconHub-Web` và `ReconHub-Worker`) qua NSSM với cấu hình xoay vòng log, tự khởi động lại khi crash.
  - `uninstall-services.ps1`: Dừng và gỡ bỏ an toàn các dịch vụ.
  - `backup-task.ps1`: Đăng ký Task Scheduler sao lưu SQLite database hàng ngày lúc 01:00 AM.
  - `README.md`: Hướng dẫn chi tiết triển khai trên Windows Server.
- Kiểm thử tạo server Waitress thành công trên cổng 8052.

### Bước 2 — 2026-11-01
- Xây dựng toàn bộ cấu hình triển khai Linux tại `deploy/linux/`:
  - `reconhub-web.service`: Systemd unit cho Gunicorn WSGI server.
  - `reconhub-worker.service`: Systemd unit cho Worker nền.
  - `reconhub-backup.service` & `reconhub-backup.timer`: Systemd timer tự động sao lưu hàng ngày lúc 01:00 AM.
  - `nginx.conf`: Mẫu cấu hình Nginx reverse proxy với timeout 600s, max body 100M và bộ nhớ đệm tĩnh.
  - `install.sh`: Script cài đặt tự động tạo system user `reconhub`, phân quyền và kích hoạt service.
  - `README.md`: Hướng dẫn triển khai và vận hành trên Ubuntu/RHEL.

### Bước 3 — 2026-11-01
- Triển khai lệnh sao lưu và khôi phục trong `app/cli.py`:
  - `app.cli backup`: Sử dụng `VACUUM INTO` tạo bản sao lưu atomic, hỗ trợ WAL checkpoint, tự động xoay vòng giữ tối đa 14 bản sao lưu gần nhất.
  - `app.cli restore`: Khôi phục an toàn database từ bản lưu, tạo bản dự phòng trước khi ghi đè và dọn dẹp file WAL/SHM.
- Cấu hình xoay vòng log với `RotatingFileHandler` (10 MB/file, 5 bản backup) trong `app/core/logging.py`.
- Viết unit test `tests/unit/test_cli_backup.py` kiểm thử toàn vẹn sao lưu, xoay vòng 14 bản và khôi phục database.

### Bước 4 — 2026-11-01
- Triển khai bài kiểm thử hiệu năng đối soát 1.000.000 dòng tổng hợp trong `tests/unit/test_engine_benchmark.py` (`test_engine_benchmark_1m_rows`).
- Kết quả đo đạc thực tế:
  - Sinh dữ liệu 1.000.000 dòng: 1.92 giây
  - Gom nhóm (Aggregate) 1.000.000 dòng Excel -> 500.000 nhóm: 9.49 giây
  - Gom nhóm (Aggregate) 500.000 dòng DB -> 500.000 nhóm: 5.23 giây
  - So khớp (Compare Full Outer Join) 500.000 nhóm: 18.21 giây
  - **Tổng thời gian xử lý lõi engine: 32.93 giây** (Vượt xa mục tiêu spec 07 mục 5 là ≤ 120 giây).

### Bước 5 — 2026-11-01
- Hoàn thiện tài liệu vận hành toàn diện `docs/OPERATIONS.md`:
  - Kiến trúc tổng thể và mô hình triển khai kép (Windows Service + NSSM / Linux Systemd + Gunicorn + Nginx).
  - Quy trình nâng cấp 5 bước an toàn không gián đoạn dịch vụ.
  - Chiến lược sao lưu, khôi phục thảm họa (Disaster Recovery) và chính sách lưu giữ 14 ngày.
  - Xử lý sự cố vận hành: giải phóng run treo (stale jobs), xoay vòng khóa mã hóa Fernet (`RECON_SECRET_KEY`), di trú dữ liệu SQLite sang Oracle RECON_APP, và dọn dẹp dữ liệu tạm theo yêu cầu người dùng.
- Vượt qua toàn bộ các cổng kiểm định chất lượng:
  - `ruff check`: All checks passed!
  - `mypy`: Success: no issues found in 92 source files.
  - `pytest`: 292 passed, 5 skipped (Oracle test server).
  - `pytest e2e`: 10 passed (100% Playwright UI screens and workflows).
