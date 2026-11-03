# Danh sách task

Bảng tổng các task, chia theo giai đoạn GĐ0–GĐ3 (docs/PRD.md Phần G). Bảng này là nguồn của `uv run poe tasks-dashboard` (hoặc `python scripts/tasks_dashboard.py`): giữ đúng các cột #, Task, Trạng thái, Phụ thuộc, Nhánh git.

| # | Task | Trạng thái | Phụ thuộc | Nhánh git |
|---|---|---|---|---|
| 00 | [00-repo-setup](00-repo-setup/task.md) — Khung repo Python trên Windows, SQLite + Alembic, poe, CI | ✅ | — | feat/00-repo-setup |
| 01 | [01-auth-users](01-auth-users/task.md) — Người dùng trên RECON_APP, đăng nhập, phân quyền 4 vai trò | ✅ | 00 | feat/01-auth-users |
| 02 | [02-data-sources](02-data-sources/task.md) — Data Source: nguồn Oracle và đích lưu RECON_APP | ✅ | 01 | feat/02-data-sources |
| 03 | [03-template-config](03-template-config/task.md) — TemplateConfig, version và service template | ✅ | 02 | feat/03-template-config |
| 04 | [04-excel-reader](04-excel-reader/task.md) — Đọc Excel, chuẩn hóa, control total, nạp dữ liệu tạm | ✅ | 00 | feat/04-excel-reader |
| 05 | [05-db-fetch](05-db-fetch/task.md) — SQL sinh từ bảng/cột, SQL guard, fetch Oracle qua VPN | ✅ | 02, 03 | feat/05-db-fetch |
| 06 | [06-compare-engine](06-compare-engine/task.md) — Gộp, ghép, so sánh, trạng thái, summary, export | ✅ | 04, 05 | feat/06-compare-engine |
| 07 | [07-run-queue-worker](07-run-queue-worker/task.md) — Run, hàng đợi, worker, dry-run, xóa dữ liệu tạm theo yêu cầu | ✅ | 03, 06 | feat/07-run-queue-worker |
| 08 | [08-app-shell-ui](08-app-shell-ui/task.md) — Component Dash Mantine, AppShell, Templates, Data Sources, Người dùng | ✅ | 01, 02, 03, 07 | feat/08-app-shell-ui |
| 09 | [09-template-wizard-ui](09-template-wizard-ui/task.md) — Wizard đăng ký template 5 bước và Sơ đồ diễn giải | ✅ | 07, 08 | feat/09-template-wizard-ui |
| 10 | [10-new-run-ui](10-new-run-ui/task.md) — Màn Chạy đối soát | ✅ | 07, 08 | feat/10-new-run-ui |
| 11 | [11-run-result-ui](11-run-result-ui/task.md) — Màn Kết quả run, grid động, Đã kiểm tra xong | ✅ | 07, 08 | feat/11-run-result-ui |
| 12 | [12-export-history](12-export-history/task.md) — Lịch sử run (xóa nhiều run), Dashboard tối thiểu, hoàn thiện MVP | ✅ | 10, 11 | feat/12-export-history |
| 13 | [13-metadata-migration](13-metadata-migration/task.md) — Chuyển RECON_APP từ SQLite sang Oracle, xóa bản lưu SQLite cũ | ✅ | 02, 12 | feat/13-metadata-migration |
| 14 | [14-issue-handling](14-issue-handling/task.md) — Xử lý chênh lệch | ✅ | 12 | feat/14-issue-handling |
| 15 | [15-dashboard-compare](15-dashboard-compare/task.md) — Dashboard đầy đủ và so sánh hai run | ✅ | 12 | feat/15-dashboard-compare |
| 16 | [16-production-readiness](16-production-readiness/task.md) — Triển khai trên Windows và Linux (không Docker) | ✅ | 00–15 | feat/16-production-readiness |
| 17 | [17-lookup-codes](17-lookup-codes/task.md) — Quản lý danh mục Lookup Code & Lookup Type dùng chung | ⬜ | 01, 08, 14 | feat/17-lookup-codes |

Thiết kế: 11 màn (designs/components/Screen01–Screen11), 13 thành phần, Gallery. Giao diện dựng bằng Dash Mantine Components.

## Thứ tự làm đề xuất
- **00 → 01 → 02** nền: repo Python trên Windows, SQLite + Alembic, người dùng và đăng nhập, Data Source Oracle qua VPN.
- **03 → 04 → 05 → 06 → 07** engine và template (04 làm song song với 01–03 được). Xong 07: `uv run poe demo-run` chạy DTP end-to-end, có xóa dữ liệu tạm theo yêu cầu.
- **08 → 09, 10, 11 → 12** giao diện MVP. Xong 12 đưa lên UAT.
- **13** chuyển RECON_APP sang Oracle khi cần. **14, 15 → 16** mở rộng và triển khai.

## Đã chốt (31/10/2026)
- Toàn Python: Dash + dash-mantine-components + dash-ag-grid, Polars. Code bằng Google Antigravity (AGENTS.md, .agents/rules, .agents/skills).
- Không Docker. Dev trên Windows, chạy Python trực tiếp, Oracle server qua VPN (oracledb Thin). Lệnh qua poethepoet (`uv run poe …`). Script hỗ trợ viết bằng Python.
- RECON_APP trên SQLite, chuyển được sang Oracle (task 13); user/password schema Oracle đăng ký ở Data Sources.
- Người dùng và phân quyền lưu trong RECON_APP, đăng nhập bằng user của ứng dụng; mật khẩu tự do (không rỗng); không Entra ID.
- Dữ liệu tạm và file SQLite cũ chỉ xóa khi người dùng yêu cầu; hệ thống chỉ cảnh báo.
- Nguồn DB của template khai báo bằng bảng/view + cột lọc.
- Đối tượng test trên Oracle do người dùng tạo tay bằng `scripts/oracle/*.sql`.
- Task 16 viết hướng dẫn triển khai cho cả Windows và Linux.

## Điểm cần quyết định
- **CI:** GitHub Actions, Azure DevOps hay chưa cần. (task 00)
- **Host/service UAT/PROD và user chỉ đọc** cho nguồn thật; tên bảng/view DTP thật. (task 02, 05; không chặn)
- **Giới hạn:** 50MB/file, 1 triệu dòng/phía, khoảng tìm kiếm tối đa 93 ngày, cảnh báo dữ liệu tạm 5GB / 30 ngày – xác nhận hoặc đổi.
- **Thư viện cần hỏi trước khi cài:** axe-core cho playwright (12), waitress/gunicorn (16).
- **Server UAT/PROD** Windows hay Linux, có reverse proxy/HTTPS không. (task 16)

Mỗi decisions.md liệt kê câu hỏi còn mở của task đó.
