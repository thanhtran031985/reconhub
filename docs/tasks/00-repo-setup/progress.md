# Tiến độ — 00-repo-setup

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | pyproject + poe + config | ✅ | 2026-10-31 | 7c80f5e |
| 2 | Schema + Alembic trên SQLite | ✅ | 2026-10-31 | b75e730 |
| 3 | Oracle test qua VPN | ✅ | 2026-10-31 |  |
| 4 | Dash khung + theme + health | 🔄 |  |  |
| 5 | Worker khung + poe dev | ⬜ |  |  |
| 6 | Lint, typecheck, CI, cập nhật AGENTS.md mục Lệnh | ⬜ |  |  |

## Nhật ký
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
