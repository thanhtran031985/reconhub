# 16-production-readiness — Triển khai trên Windows và Linux (không Docker)

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ3
- Phụ thuộc: 00–15
- Nhánh git: feat/16-production-readiness

## Mục tiêu
Có hướng dẫn và script triển khai chạy trực tiếp trên server Windows (waitress + Windows Service) và Linux (gunicorn + systemd), sao lưu SQLite, log, healthcheck, bench 1 triệu dòng, tài liệu vận hành.

## Phạm vi
- app/wsgi.py dùng chung; thêm waitress (Windows) và gunicorn (Linux) làm optional dependency (hỏi trước)
- deploy/windows/: install-services.ps1 (NSSM tạo ReconHub-Web, ReconHub-Worker, tài khoản dịch vụ, thư mục log), backup-task.ps1 (Task Scheduler gọi app.cli backup), README
- deploy/linux/: reconhub-web.service, reconhub-worker.service, reconhub-backup.timer, nginx.conf mẫu, install.sh, README
- app.cli backup (VACUUM INTO, giữ 14 bản)
- Bench 1.000.000 dòng (spec 07 mục 5)
- docs/OPERATIONS.md: cài đặt, nâng cấp (dừng → cập nhật → uv sync --frozen → db-migrate → chạy), sao lưu/khôi phục, xử lý job treo, xoay RECON_SECRET_KEY, đổi DB RECON_APP, xóa dữ liệu tạm định kỳ thủ công

## Ngoài phạm vi
- Docker

## Thiết kế
- (Không có giao diện)

## Spec liên quan
- docs/specs/06 mục 6–8
- docs/specs/07 mục 5
- docs/specs/08

## Quyết định kiến trúc
- Web và worker cùng máy, data/ trên ổ local

## Các bước
### Bước 1 — Windows
- Làm: waitress, NSSM, backup task
- Test viết trước: chạy thử trên máy Windows: dịch vụ tự chạy lại sau khởi động
- Kiểm tra: Restart máy, mở http://localhost:8050

### Bước 2 — Linux
- Làm: gunicorn, systemd, nginx mẫu
- Test viết trước: kiểm cú pháp unit (`systemd-analyze verify`) trên máy Linux nếu có
- Kiểm tra: Đọc lại + chạy thử nếu có máy Linux

### Bước 3 — Backup + log
- Làm: Backup + log
- Test viết trước: backup tạo file mở được; log xoay vòng
- Kiểm tra: `uv run poe test`

### Bước 4 — Bench
- Làm: Bench
- Test viết trước: pytest -m bench
- Kiểm tra: ghi số liệu vào progress.md

### Bước 5 — Tài liệu vận hành
- Làm: OPERATIONS.md
- Test viết trước: —
- Kiểm tra: Đọc lại

## Chấp nhận khi
- [ ] Cài được trên Windows theo hướng dẫn
- [ ] Hướng dẫn Linux đầy đủ
- [ ] Run 1 triệu dòng ≤ 120 giây
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- Server UAT/PROD là Windows hay Linux (khi đã biết)?
- Có cần reverse proxy (IIS/Nginx) và HTTPS nội bộ không?
