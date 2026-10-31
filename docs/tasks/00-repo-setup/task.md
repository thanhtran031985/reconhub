# 00-repo-setup — Khung repo Python trên Windows, SQLite + Alembic, poe, CI

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ0
- Phụ thuộc: —
- Nhánh git: feat/00-repo-setup

## Mục tiêu
Có repo Python chạy được trên Windows (không Docker): Dash + Mantine hiển thị khung trống theo token, /health trả trạng thái DB, worker khởi động, RECON_APP là file SQLite (WAL) do Alembic tạo đủ bảng spec 02, các lệnh `uv run poe …` trong AGENTS.md chạy được; kết nối thử Oracle test qua VPN.

## Phạm vi
- pyproject.toml (uv) + `[tool.poe.tasks]` đủ lệnh ở AGENTS.md mục Lệnh; uv.lock
- app/core/config.py (Pydantic Settings đọc .env); đường dẫn bằng pathlib, tương đối từ thư mục dự án
- app/db/metadata.py: TOÀN BỘ bảng spec 02 mục 1–7; TypeDecorator DecimalText, JsonText; naming convention
- app/db/engine.py: SQLite PRAGMA (WAL, foreign_keys, busy_timeout, synchronous, auto_vacuum khi tạo); Oracle qua oracledb Thin; app/db/dialect.py khung (claim_job, upsert)
- Alembic: env.py dùng metadata, `render_as_batch` cho SQLite, revision `0001_init`
- app/ui/app.py: Dash `use_pages=True`, MantineProvider(theme), trang trắng 'ReconHub'; `poe theme` chạy scripts/gen_dmc_theme.py và copy designs/tokens.css vào app/ui/assets/
- app/routes/health.py; app/wsgi.py (`server = app.server`)
- worker/__main__.py: vòng poll rỗng, heartbeat log, dừng sạch Ctrl+C/SIGTERM (Windows và Linux)
- poe dev: chạy Dash và worker song song (2 process, dừng cả hai khi Ctrl+C)
- tests: fixture `sqlite_url` (file tạm) và `oracle_test` (skip khi thiếu ORACLE_TEST_*); marker `oracle`; structlog ghi logs/
- Script tasks_dashboard.py, design_system.py chạy qua poe
- CI (GitHub Actions hoặc Azure DevOps, hỏi trước): lint, typecheck, test (không Oracle) trên windows-latest và ubuntu-latest

## Ngoài phạm vi
- Đăng nhập, nghiệp vụ, page thật
- Docker

## Thiết kế
- designs/tokens.json, designs/tokens.css, designs/README.md mục Ánh xạ sang Dash Mantine

## Spec liên quan
- docs/specs/01_architecture_adr.md (ADR-011, ADR-013)
- docs/specs/02_database_schema.md
- docs/specs/06_security_ops.md mục 8

## Quyết định kiến trúc
- Gói: dash>=3, dash-mantine-components>=2.8, dash-ag-grid, dash-iconify, flask, pydantic, pydantic-settings, polars, fastexcel, xlsxwriter, openpyxl (test/inspect), sqlalchemy>=2, alembic, oracledb, cryptography, argon2-cffi, structlog; dev: pytest, pytest-cov, pytest-playwright, ruff, mypy, poethepoet. waitress/gunicorn để task 16
- Đọc https://www.dash-mantine-components.com/llms trước khi viết code UI
- Theme không dùng màu mặc định Mantine

## Các bước
### Bước 1 — pyproject + poe + config
- Làm: pyproject, poe tasks, config, .env.example (giữ nguyên biến có sẵn, thêm nếu thiếu)
- Test viết trước: tests/test_config.py: đọc .env mẫu, đường dẫn tương đối đúng trên Windows
- Kiểm tra: `uv sync`; `uv run poe --help` liệt kê đủ lệnh

### Bước 2 — Schema + Alembic trên SQLite
- Làm: metadata.py, TypeDecorator, engine.py, revision 0001
- Test viết trước: tests/integration/test_migrations.py: upgrade head 2 lần; downgrade base → upgrade head; PRAGMA journal_mode=wal; Decimal 0.1+0.2 lưu/đọc chính xác; JSON; thời gian ms
- Kiểm tra: `uv run poe db-migrate` 2 lần; `uv run poe test`

### Bước 3 — Oracle test qua VPN
- Làm: oracle_test fixture, kiểm tra kết nối + đọc 1 dòng SRC_FACT_INVOICE_DTP; Alembic upgrade/downgrade trên ORACLE_TEST_APP_USER
- Test viết trước: tests/integration/test_oracle_smoke.py (marker oracle)
- Kiểm tra: `uv run poe test-oracle` (VPN; người dùng chạy và dán kết quả)

### Bước 4 — Dash khung + theme + health
- Làm: app.py, theme, assets, /health, wsgi
- Test viết trước: test: theme không chứa màu ngoài token; app khởi tạo; /health trả db up
- Kiểm tra: `uv run poe dev` → http://localhost:8050 đúng font, màu

### Bước 5 — Worker khung + poe dev
- Làm: worker, chạy song song
- Test viết trước: test vòng lặp dừng khi có tín hiệu
- Kiểm tra: `uv run poe dev` thấy log heartbeat; Ctrl+C dừng cả hai

### Bước 6 — Lint, typecheck, CI, cập nhật AGENTS.md mục Lệnh
- Làm: ruff, mypy strict, workflow; chỉ sửa mục Lệnh nếu khác thực tế (ghi decisions.md)
- Test viết trước: —
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Chấp nhận khi
- [ ] Máy Windows mới: `uv sync`, `uv run poe db-migrate`, `uv run poe dev` chạy được
- [ ] test-oracle xanh khi có VPN, skip khi không
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- CI dùng GitHub Actions hay Azure DevOps (hay chưa cần)?
