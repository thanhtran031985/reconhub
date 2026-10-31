# Kế hoạch — 00-repo-setup

Khung repo Python trên Windows, SQLite + Alembic, poe, CI

## Phiên bản công nghệ
- Python: `~=3.12.0` (quản lý bởi `uv`)
- Quản lý gói & tác vụ: `uv >= 0.9.0`, `poethepoet >= 0.32.0`
- Web & Giao diện: `dash ~= 3.0.0`, `dash-mantine-components >= 2.8.0`, `dash-ag-grid >= 31.3.0`, `dash-iconify >= 0.1.2`, `flask >= 3.0.0`
- CSDL & Migration: `sqlalchemy ~= 2.0.36`, `alembic ~= 1.14.0`, `oracledb ~= 2.5.0`
- Dữ liệu & Tiện ích: `pydantic ~= 2.10.0`, `pydantic-settings ~= 2.7.0`, `polars ~= 1.20.0`, `fastexcel ~= 0.12.0`, `xlsxwriter ~= 3.2.0`, `openpyxl ~= 3.1.5`, `cryptography ~= 44.0.0`, `argon2-cffi ~= 23.1.0`, `structlog ~= 25.1.0`
- Kiểm thử & Chất lượng mã: `pytest ~= 8.3.0`, `pytest-cov ~= 6.0.0`, `pytest-playwright ~= 0.6.0`, `ruff ~= 0.9.0`, `mypy ~= 1.14.0`

## Chi tiết các bước thực hiện

### Bước 1 — pyproject + poe + config
- **Mục tiêu:** Thiết lập cấu hình gói, các lệnh poe, đọc cấu hình ứng dụng từ `.env` bằng Pydantic Settings với đường dẫn `pathlib`.
- **File tạo / sửa:**
  - `pyproject.toml`: Khai báo metadata dự án, dependencies, dev-dependencies, cấu hình `[tool.poe.tasks]` đầy đủ theo AGENTS.md, cấu hình ruff, mypy, pytest.
  - `.python-version`: Ghim phiên bản `3.12`.
  - `app/core/config.py`: Lớp `Settings` (kế thừa `BaseSettings` từ `pydantic-settings`), đọc biến môi trường, chuyển đổi đường dẫn sang `pathlib.Path` tuyệt đối từ thư mục gốc.
  - `app/core/__init__.py`
  - `app/cli.py`: Khung CLI tối thiểu bằng `argparse` hỗ trợ các sub-command với thông báo placeholder.
  - `.env.example`: Rà soát và bổ sung nếu còn thiếu biến.
- **Test viết trước (TDD):**
  - `tests/test_config.py`:
    - Đọc các giá trị mặc định từ `.env.example`.
    - Kiểm tra các đường dẫn `RECON_STORAGE_DIR`, `BACKUP_DIR`, đường dẫn file SQLite là `Path` hợp lệ trên Windows.
    - Kiểm tra cấu hình boolean và số nguyên chuyển đổi chuẩn xác.
- **Kiểm tra:**
  - `uv sync`
  - `uv run poe --help`
  - `uv run pytest tests/test_config.py -v`

### Bước 2 — Schema + Alembic trên SQLite
- **Mục tiêu:** Định nghĩa toàn bộ schema Spec 02 bằng SQLAlchemy Core, các TypeDecorator (`DecimalText`, `JsonText`), kết nối SQLite PRAGMA tối ưu (WAL, foreign_keys, busy_timeout) và migration đầu tiên với batch mode.
- **File tạo / sửa:**
  - `app/db/metadata.py`: Đầy đủ các bảng từ mục 1 đến 7 của Spec 02 (`RECON_USER`, `RECON_USER_ROLE`, `RECON_LOGIN_LOG`, `RECON_AUDIT_LOG`, `RECON_APP_SETTING`, `RECON_DATA_SOURCE`, `RECON_TEMPLATE`, `RECON_TEMPLATE_VERSION`, `RECON_FILE`, `RECON_EXCEL_LOAD`, `RECON_EXCEL_ROW`, `RECON_RUN`, `RECON_RUN_QUEUE`, `RECON_RUN_SUMMARY`, `RECON_RESULT_ROW`, `RECON_RESULT_DIFF`, `RECON_INVALID_ROW`, `RECON_ISSUE_REASON`, `RECON_ISSUE`, `RECON_PURGE_LOG`, `RECON_METADATA_MIGRATION`), naming convention tường minh, kiểu `DecimalText` và `JsonText`.
  - `app/db/engine.py`: Quản lý SQLAlchemy engine, hàm `init_sqlite_db` thiết lập PRAGMA (`journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=30000`, `synchronous=NORMAL`, `auto_vacuum=INCREMENTAL`).
  - `app/db/dialect.py`: Khung dialect trừu tượng hóa khác biệt giữa SQLite và Oracle (chức năng claim job, upsert).
  - `app/db/__init__.py`
  - `alembic.ini`: Cấu hình Alembic.
  - `migrations/env.py`: Cấu hình Alembic sử dụng `target_metadata = metadata`, bật `render_as_batch=True` khi chạy trên SQLite.
  - `migrations/script.py.mako`
  - `migrations/versions/0001_init.py`: Migration ban đầu sinh đủ toàn bộ các bảng.
- **Test viết trước (TDD):**
  - `tests/integration/test_migrations.py`:
    - Tạo SQLite DB tạm, chạy `upgrade head` thành công và idempotence (chạy lần 2 không lỗi).
    - Kiểm tra `downgrade base` và `upgrade head` lại.
    - Kiểm tra PRAGMA `journal_mode=wal`, `foreign_keys=1`.
    - Kiểm tra ghi/đọc `DecimalText` (đảm bảo độ chính xác của số thập phân, ví dụ `0.1 + 0.2`).
    - Kiểm tra ghi/đọc `JsonText` hợp lệ và từ chối chuỗi JSON sai cú pháp.
- **Kiểm tra:**
  - `uv run poe db-migrate` 2 lần
  - `uv run pytest tests/integration/test_migrations.py -v`

### Bước 3 — Oracle test qua VPN
- **Mục tiêu:** Tạo fixture kiểm thử Oracle `python-oracledb` Thin mode, tự động skip an toàn khi môi trường thiếu các biến `ORACLE_TEST_*`. Người dùng chọn bỏ qua việc chạy test Oracle qua VPN thực tế trong task này.
- **File tạo / sửa:**
  - `tests/conftest.py`: Fixture `sqlite_url` (file tạm), fixture `oracle_test` (đọc biến môi trường, kiểm tra kết nối; tự gọi `pytest.skip` nếu thiếu thông tin hoặc timeout).
  - `tests/integration/test_oracle_smoke.py`: Test đánh dấu `@pytest.mark.oracle`, đọc thử 1 dòng từ `SRC_FACT_INVOICE_DTP` nếu có VPN và schema test, skip an toàn khi thiếu biến.
- **Test viết trước (TDD):**
  - `tests/integration/test_oracle_smoke.py`:
    - Kết nối thử tới Oracle và thực hiện `SELECT 1 FROM DUAL`.
    - Truy vấn thử bảng test nguồn `SRC_FACT_INVOICE_DTP` với user chỉ đọc.
- **Kiểm tra:**
  - `uv run pytest -m "not oracle" -v`
  - `uv run poe test-oracle` (skip an toàn khi thiếu biến môi trường hoặc chưa bật VPN)

### Bước 4 — Dash khung + theme + health
- **Mục tiêu:** Khởi tạo ứng dụng Dash với `use_pages=True`, cấu hình `dmc.MantineProvider` với theme sinh từ token, tích hợp route kiểm tra trạng thái `/health` và module WSGI.
- **File tạo / sửa:**
  - `scripts/gen_dmc_theme.py`: Cập nhật thêm bước copy file `designs/tokens.css` sang `app/ui/assets/tokens.css`.
  - `app/ui/theme.py`: File theme sinh tự động.
  - `app/ui/app.py`: Khởi tạo Dash app, nạp theme, bọc `dmc.MantineProvider`, tiêu đề 'ReconHub', hỗ trợ Dash Pages.
  - `app/ui/layout.py`: Layout gốc chứa `dcc.Location`, thông báo banner, và vùng hiển thị `dash.page_container`.
  - `app/ui/pages/home.py`: Trang trắng mặc định đón trang chủ.
  - `app/routes/health.py`: Blueprint Flask `/health` kiểm tra kết nối DB và trả JSON status.
  - `app/wsgi.py`: Cung cấp biến `server = app.server`.
- **Test viết trước (TDD):**
  - `tests/test_ui_smoke.py`:
    - Kiểm tra theme không chứa mã màu nằm ngoài token quy định.
    - Khởi tạo Dash app không gặp exception.
    - Gọi endpoint Flask `/health` trả về mã HTTP 200 và trạng thái `db: up`.
- **Kiểm tra:**
  - `uv run poe theme`
  - `uv run pytest tests/test_ui_smoke.py -v`

### Bước 5 — Worker khung + poe dev
- **Mục tiêu:** Tạo tiến trình worker nền với vòng lặp poll rỗng, log heartbeat định kỳ bằng `structlog`, bắt tín hiệu dừng sạch (Ctrl+C / SIGTERM / SIGINT) trên Windows và Linux; cấu hình lệnh `poe dev` chạy đồng thời Dash và Worker.
- **File tạo / sửa:**
  - `worker/__main__.py`: Vòng lặp lấy job khung, xử lý graceful shutdown an toàn trên Windows (`signal.SIGINT`, `signal.SIGBREAK`, `KeyboardInterrupt`).
  - `worker/__init__.py`
  - `app/core/logging.py`: Cấu hình `structlog` ghi log console và file `logs/app.log`.
  - `scripts/dev_server.py`: Script khởi chạy cả Dash server và Worker trong 2 subprocess, lắng nghe phím tắt và tắt đồng thời cả hai tiến trình khi dừng.
- **Test viết trước (TDD):**
  - `tests/test_worker_lifecycle.py`:
    - Kiểm tra worker khởi động và dừng sạch khi nhận cờ dừng (stop event) mà không rò rỉ tiến trình.
- **Kiểm tra:**
  - `uv run pytest tests/test_worker_lifecycle.py -v`

### Bước 6 — Lint, typecheck, CI, cập nhật AGENTS.md mục Lệnh
- **Mục tiêu:** Đảm bảo toàn bộ mã nguồn đạt chuẩn lint (ruff) và typecheck nghiêm ngặt (mypy strict), thiết lập workflow CI GitHub Actions, cập nhật bảng tiến độ dashboard.
- **File tạo / sửa:**
  - `.github/workflows/ci.yml`: Workflow GitHub Actions chạy lint, typecheck, test trên windows-latest và ubuntu-latest.
  - `docs/tasks/00-repo-setup/progress.md`: Cập nhật tiến độ sau khi hoàn thành các bước.
  - `docs/tasks/00-repo-setup/decisions.md`: Ghi lại các quyết định kỹ thuật phát sinh.
- **Kiểm tra:**
  - `uv run poe lint`
  - `uv run poe typecheck`
  - `uv run poe test`
  - `uv run poe tasks-dashboard`
