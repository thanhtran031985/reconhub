# ReconHub — Hướng dẫn cho agent (Antigravity)

File này luôn được nạp. Quy tắc theo vùng code ở `.agents/rules/` (tự nạp theo glob), quy trình lặp lại ở `.agents/skills/`.

## Dự án
ReconHub là web app nội bộ đối soát file Excel với Oracle. Người dùng đăng ký **template** (mapping cột Excel và cột DB về trường logic; bảng/view nguồn + cột lọc Từ ngày, Đến ngày, Đơn vị; profile gồm Group by và Measure SUM/COUNT, sai số), rồi upload file, nhập khoảng ngày giờ tìm kiếm và chạy. Kết quả: Khớp, Lệch giá trị, Thiếu trong DB, Thiếu trong Excel, Không nhất quán, Trùng khóa, Không hợp lệ. Dữ liệu Excel đã nạp là **dữ liệu tạm**, người dùng **chủ động xóa** (không tự xóa).

- Vai trò: Admin, Template Owner, Operator, Viewer. Người dùng và vai trò lưu trong RECON_APP; đăng nhập bằng username/mật khẩu của ứng dụng.
- File mẫu (dữ liệu tổng hợp theo cấu trúc file DTP thật): `samples/dtp_sample_200.xlsx`; template mẫu `samples/templates/DTP_HOA_DON_TAC_NGHIEP.json`.
- Tài liệu: `docs/PRD.md` (theo màn hình), `docs/specs/00–08` (nguồn chi tiết), `docs/DESIGN_SYSTEM.md`, `designs/` (CHỈ ĐỌC).

## Môi trường
- Máy dev: **Windows**, chạy Python trực tiếp (không Docker). Kết nối Oracle server qua **VPN** bằng python-oracledb chế độ Thin (không cần Oracle Client).
- Đối tượng test trên Oracle do người dùng tạo tay bằng `scripts/oracle/*.sql`. Agent KHÔNG tự tạo/xóa đối tượng trên Oracle; test tích hợp Oracle chỉ đọc bảng test đã có và tự **skip** khi thiếu biến `ORACLE_TEST_*` trong môi trường.
- Lệnh chạy bằng **poethepoet**: `uv run poe <tên>` (khai báo trong `pyproject.toml`), dùng được trên Windows và Linux. Lệnh shell trong task viết dạng PowerShell-compatible; đường dẫn dùng `pathlib`, không hardcode `/` hay `\`.

## Stack (toàn Python)
- Giao diện: Dash 3 + dash-mantine-components 2.x (Mantine v8), dash-ag-grid, dash-iconify (bộ `lucide:`), Mermaid nạp từ `app/ui/assets/`. Trước khi viết code UI, đọc trang của component cần dùng ở https://www.dash-mantine-components.com/llms.
- Nghiệp vụ: Python 3.12, Pydantic v2, Polars, fastexcel/calamine, XlsxWriter, SQLAlchemy 2 Core, Alembic, python-oracledb (Thin), cryptography, argon2-cffi, structlog. Quản lý gói: uv. Lệnh: poethepoet. Test: pytest, pytest-playwright. Lint/type: ruff, mypy.
- RECON_APP (người dùng, metadata, hàng đợi, dữ liệu Excel tạm, kết quả): mặc định **SQLite** (`data/recon_app.db`, WAL). Chuyển được sang **Oracle** (spec 08).
- Nguồn đối soát: Oracle, khai báo ở Data Sources, user chỉ đọc.
- Đăng nhập: bảng `RECON_USER` trên RECON_APP, mật khẩu băm argon2, phiên Flask. Không dùng Entra ID.
- Chạy server: dev dùng server Dash; triển khai Windows dùng waitress + Windows Service, Linux dùng gunicorn + systemd (task 16).

## Cấu trúc mã
```
app/ui/          app.py, theme.py (sinh ra), layout/, pages/ (dash.register_page), components/, assets/
app/services/    nghiệp vụ, trả ServiceResult
app/engine/      hàm thuần: reader, normalize, filters, aggregate, sql_builder, fetch, compare, export
app/repo/ app/db/  SQLAlchemy Core: metadata.py (nguồn sự thật schema), engine.py, dialect.py (SQLite | Oracle)
app/schemas/     Pydantic: TemplateConfig, RunParams, ServiceResult, errors.py
app/core/        config, auth (mật khẩu, phiên), crypto, audit, time
app/routes/      Flask: /health, /download/*, /login, /logout
app/cli.py       lệnh quản trị: create-admin, reset-password, purge-temp, migrate-metadata
worker/          lấy job từ RECON_RUN_QUEUE
migrations/      Alembic (SQLite batch mode và Oracle)
tests/           unit, integration, golden/, e2e/
scripts/         tasks_dashboard.py, design_system.py, gen_dmc_theme.py, oracle/*.sql
data/ storage/ backup/   SQLite, file upload/cache/export, bản sao lưu (gitignore)
```

## Cấu trúc task
`docs/tasks/README.md` là bảng tổng (cột #, Task, Trạng thái, Phụ thuộc, Nhánh git). Mỗi task `docs/tasks/NN-slug/` có `task.md` (yêu cầu, KHÔNG tự sửa), `progress.md` (agent cập nhật sau mỗi bước), `plan.md` (kế hoạch đã duyệt), `decisions.md`, `_archive/`. Nhánh `feat/NN-slug`. `docs/tasks/dashboard.html` sinh bởi `uv run poe tasks-dashboard`, không sửa tay.
Trạng thái: ⬜ chưa làm · 🔄 đang làm · ❓ có code chưa rà soát · ⚠️ khác task.md · ❌ thiếu · ✅ xong.

## Quy trình khi làm một task (chi tiết: skill `lam-task`)
- Mở phiên mới hoặc sau khi ngữ cảnh bị nén: đọc `docs/tasks/README.md` → `task.md` → `progress.md` → `decisions.md`, tiếp tục từ bước dở, không làm lại bước ✅.
- Luôn lập **Implementation Plan** trước. Khi được duyệt: chép nguyên văn vào `plan.md`, tạo nhánh `feat/NN-slug`, đổi trạng thái 🔄.
- Làm đúng thứ tự các bước trong task.md. Viết test hành vi trước (thấy đỏ) rồi code cho xanh.
- Sau MỖI bước: chạy phần "Kiểm tra"; cập nhật `progress.md`; chạy `uv run poe tasks-dashboard`; báo cáo ngắn; đề xuất commit `NN-slug: step N — <mô tả>`; **DỪNG** chờ "continue". Chỉ commit khi được đồng ý.
- Khác task.md/spec/thiết kế: ghi `decisions.md`. Mơ hồ hoặc mâu thuẫn: DỪNG và hỏi. Chi tiết nhỏ: tự suy ra từ spec, báo đã suy ra gì.
- Không cài package ngoài danh sách Stack khi chưa hỏi.
- Xong task: đổi trạng thái ✅ trong `docs/tasks/README.md`.

## Quy tắc code (mọi task)
- Nghiệp vụ chỉ ở `app/services` và `app/engine`. Callback Dash chỉ lấy người dùng hiện tại, validate bằng Pydantic, gọi service, dựng lại component.
- Service nhận `ctx` (người dùng hiện tại), tự kiểm quyền, trả `ServiceResult {ok, data | code, message, details}`; `code` từ `app/schemas/errors.py`; `message` tiếng Việt có dấu. Không để exception lọt ra giao diện.
- Truy cập RECON_APP chỉ qua SQLAlchemy Core trong `app/repo`. Khác biệt SQLite/Oracle gom ở `app/db/dialect.py`.
- Đổi schema bằng Alembic revision chạy được trên SQLite (batch mode) và Oracle.
- Không có secret trong component, `dcc.Store`, log, audit. Mật khẩu người dùng băm argon2; mật khẩu Data Source mã hóa Fernet.
- Chỉ dùng design token (theme DMC sinh từ `designs/tokens.json`); không viết hex/px trong page.
- Chỉ sửa trong phạm vi task. Không thêm tính năng ngoài task.md.
- Trước khi báo xong: `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh; task có giao diện chạy thêm `uv run poe e2e`.

## Quy tắc nghiệp vụ cốt lõi
- Đọc Excel: mọi cột dạng chuỗi trước, chuẩn hóa sau theo kiểu khai báo. Tiền/số lượng so bằng Decimal, không float.
- `p_from`, `p_to` là ngày giờ người dùng nhập khi chạy (giờ Việt Nam, gồm cả hai đầu), áp cho cả DB và Excel. KHÔNG lấy min/max ngày trong file. Dòng Excel ngoài khoảng phải được đếm và hiển thị.
- Nguồn DB mặc định khai báo bằng bảng/view + cột lọc; hệ thống sinh SELECT có bind param, định danh lấy từ danh sách cột của DB và được quote. SQL tự viết là chế độ nâng cao, phải qua SQL guard.
- Template có version; run ghi version đã dùng; kết quả và tham số run DONE không sửa.
- Dữ liệu tạm (Excel đã nạp, file gốc, cache) **chỉ xóa khi người dùng yêu cầu** (spec 04 mục 12). Hệ thống chỉ cảnh báo khi vượt ngưỡng. Sau khi xóa, giao diện nói rõ "Dữ liệu Excel gốc đã xóa lúc …".
- Thay đổi người dùng, template, data source, issue, mọi lần xóa dữ liệu tạm: ghi `RECON_AUDIT_LOG` trong cùng transaction.

## Giao diện (chi tiết: rule `ui-dash`)
Máy tính trước (1440×900, dùng được 1366×768). Tiếng Việt có dấu, giữ thuật ngữ Template, Profile, Measure, Group by, Data Source, Run, Dry-run. Không emoji, không dấu chấm than. Màu trạng thái luôn kèm icon và chữ. Mỗi bảng/màn có 4 trạng thái: đang tải, trống, lỗi (giữ dữ liệu cũ + Thử lại), có dữ liệu. Mã, số hóa đơn, SQL dùng font mono.

## Bảo mật môi trường
KHÔNG đọc `.env` (biến nằm trong `.env.example`; cần biến mới thì thêm vào đó và báo người dùng điền). KHÔNG ghi vào Oracle UAT/PROD. Test chỉ dùng schema test do người dùng chỉ định.

## Lệnh (`uv run poe <tên>`)
- `install` (`uv sync`), `dev` (Dash cổng 8050 + worker), `worker`, `test`, `test-engine` (không cần Oracle), `test-oracle` (cần VPN + biến ORACLE_TEST_*), `typecheck`, `lint`, `format`.
- `db-migrate` (Alembic trên `RECON_DB_URL`), `db-seed` (user mẫu, template DTP, Data Source test), `theme` (sinh theme DMC), `design-system` (sinh DESIGN_SYSTEM.md + tokens.css), `e2e`, `tasks-dashboard`.
- Quản trị: `uv run python -m app.cli create-admin`, `reset-password`, `purge-temp`, `migrate-metadata` (thêm dần theo task).
