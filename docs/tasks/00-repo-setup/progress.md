# Tiến độ — 00-repo-setup

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | pyproject + poe + config | ✅ | 2026-10-31 | 7c80f5e |
| 2 | Schema + Alembic trên SQLite | ✅ | 2026-10-31 | b75e730 |
| 3 | Oracle test qua VPN | ✅ | 2026-10-31 | b95d2b2 |
| 4 | Dash khung + theme + health | ✅ | 2026-10-31 | 4c3ad27 |
| 5 | Worker khung + poe dev | ✅ | 2026-10-31 | 469bd08 |
| 6 | Lint, typecheck, CI, cập nhật AGENTS.md mục Lệnh | ✅ | 2026-10-31 |  |

## Nhật ký
### Bước 6 — 2026-10-31 22:32
- Đã làm:
  - Cấu hình và chuẩn hóa toàn bộ mã nguồn theo Ruff linter và formatter.
  - Chuẩn hóa kiểu dữ liệu nghiêm ngặt theo Mypy strict (`19 source files checked, no issues`).
  - Thiết lập workflow CI GitHub Actions tại `.github/workflows/ci.yml` chạy trên cả `windows-latest` và `ubuntu-latest`.
  - Rà soát mục Lệnh trong `AGENTS.md` khớp hoàn toàn với cấu hình thực tế trong `pyproject.toml`.
- Kiểm tra:
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 19 source files.
  - `uv run poe test`: 8 passed, 1 skipped (test-oracle tự skip) trong 5.15s.
- Suy ra (nếu có): Thêm `disallow_untyped_calls` linh hoạt hoặc ignore tường minh khi gọi các hàm chưa có type stubs từ thư viện `dash`.
- Việc cần người làm thủ công: Không có.

### Bước 5 — 2026-10-31 22:30
- Đã làm:
  - Cấu hình logging chuẩn với structlog trong `app/core/logging.py`, ghi song song console và file `logs/app.log`.
  - Cài đặt `worker/runner.py` và `worker/__main__.py` hỗ trợ vòng lặp poll rỗng, heartbeat log, và cơ chế bắt tín hiệu dừng sạch sẽ (Ctrl+C / SIGTERM / SIGBREAK).
  - Cài đặt `scripts/dev_server.py` khởi chạy song song Dash server và Worker trong 2 subprocess, tự động dừng cả hai khi ngắt.
  - Viết test `tests/test_worker_lifecycle.py` kiểm tra vòng đời khởi động và dừng sạch của worker.
- Kiểm tra:
  - `uv run pytest tests/test_worker_lifecycle.py -v`: 1 passed trong 0.84s.
  - `uv run poe test-engine`: 8 passed, 1 deselected trong 4.83s.
- Suy ra (nếu có): Dùng subprocess quản lý cả Dash và Worker trong `scripts/dev_server.py` giúp dừng hoàn toàn tiến trình con khi nhấn Ctrl+C trên Windows.
- Việc cần người làm thủ công: Không có.

### Bước 4 — 2026-10-31 22:27
- Đã làm:
  - Cập nhật `scripts/gen_dmc_theme.py` tự động sao chép `designs/tokens.css` vào `app/ui/assets/tokens.css` và cấu hình UTF-8 stdout trên Windows.
  - Sinh theme DMC `app/ui/theme.py` chuẩn Mantine v8 từ `designs/tokens.json`.
  - Khởi tạo Dash app `app/ui/app.py` với `use_pages=True`, bọc `dmc.MantineProvider` với theme và assets.
  - Cài đặt trang đón ban đầu `app/ui/pages/home.py`.
  - Cài đặt endpoint `/health` tại `app/routes/health.py` kiểm tra kết nối DB.
  - Cung cấp entrypoint `app/wsgi.py` (`server = app.server`).
  - Viết test `tests/test_ui_smoke.py` kiểm tra token theme, khởi tạo Dash app và endpoint `/health`.
- Kiểm tra:
  - `uv run poe theme`: Sinh theme và sao chép CSS thành công.
  - `uv run poe test-engine`: 7 passed, 1 deselected trong 4.29s.
- Suy ra (nếu có): Thêm `sys.stdout.reconfigure(encoding="utf-8")` vào các script Python để chạy ổn định trên console Windows mà không bị lỗi bảng mã cp1252.
- Việc cần người làm thủ công: Không có.

### Bước 3 — 2026-10-31 22:25
- Đã làm:
  - Cài đặt fixture `oracle_test` trong `tests/conftest.py` với cơ chế kiểm tra kết nối Oracle Thin mode và tự động `pytest.skip` khi thiếu cấu hình hoặc chưa có VPN.
  - Viết test `tests/integration/test_oracle_smoke.py` có đánh dấu `@pytest.mark.oracle` để kiểm tra kết nối DUAL và truy vấn bảng `SRC_FACT_INVOICE_DTP`.
- Kiểm tra:
  - `uv run poe test-oracle`: Tự động skip an toàn (1 skipped trong 0.09s).
  - `uv run poe test-engine`: Chạy các test ngoài Oracle (4 passed, 1 deselected trong 2.78s).
- Suy ra (nếu có): Thực hiện đúng yêu cầu của người dùng về việc bỏ qua chạy test Oracle qua VPN thực tế trong phiên làm việc này.
- Việc cần người làm thủ công: Bật VPN và điền biến `ORACLE_TEST_*` trong `.env` khi cần chạy kiểm thử thực tế trên CSDL Oracle.

### Bước 2 — 2026-10-31 22:24
- Đã làm:
  - Định nghĩa toàn bộ schema Spec 02 mục 1–7 bằng SQLAlchemy Core trong `app/db/metadata.py` với TypeDecorator `DecimalText`, `JsonText`, naming convention chuẩn.
  - Cài đặt `app/db/engine.py` thiết lập PRAGMAs tối ưu cho SQLite (`wal`, `foreign_keys=ON`, `busy_timeout=30000`, `synchronous=NORMAL`, `auto_vacuum=INCREMENTAL`).
  - Cài đặt khung dialect `app/db/dialect.py` hỗ trợ claim job concurrency cho SQLite và Oracle.
  - Cấu hình Alembic `alembic.ini`, `migrations/env.py` (batch mode trên SQLite), và sinh revision `0001_init`.
  - Viết test `tests/integration/test_migrations.py` kiểm tra vòng đời migration, PRAGMAs, DecimalText (0.1 + 0.2 chính xác) và JsonText.
- Kiểm tra:
  - `uv run poe db-migrate`: Chạy thành công 2 lần (idempotent).
  - `uv run poe test`: 4 passed trong 3.95s.
- Suy ra (nếu có): Tự động tạo thư mục `data/` trong `env.py` khi chạy SQLite migration nếu thư mục chưa tồn tại.
- Việc cần người làm thủ công: Không có.

### Bước 1 — 2026-10-31 22:08
- Đã làm:
  - Khởi tạo Git repository trên nhánh `main`, cấu hình remote origin GitHub và chuyển sang nhánh `feat/00-repo-setup`.
  - Tạo `.python-version` ghim Python 3.12.
  - Tạo `pyproject.toml` định nghĩa toàn bộ dependencies, dev-dependencies, và cấu hình `[tool.poe.tasks]` cho toàn bộ lệnh trong AGENTS.md.
  - Cài đặt cấu hình ứng dụng `app/core/config.py` bằng Pydantic Settings đọc `.env`, chuẩn hóa đường dẫn `pathlib.Path` cho Windows.
  - Tạo khung CLI quản trị ban đầu `app/cli.py`.
  - Viết bộ kiểm thử `tests/test_config.py` kiểm tra cấu hình mặc định và nạp từ `.env.example`.
- Kiểm tra:
  - `uv sync`: Cài đặt thành công 71 gói với CPython 3.12.12.
  - `uv run poe --help`: Liệt kê đầy đủ 19 tasks cấu hình.
  - `uv run pytest tests/test_config.py -v`: 2 passed trong 1.01s.
- Suy ra (nếu có): Thêm CLI quản trị khung vào `app/cli.py` để các poe tasks quản trị (`create-admin`, `reset-password`,...) không bị lỗi cú pháp khi gọi.
- Việc cần người làm thủ công: Không có.
