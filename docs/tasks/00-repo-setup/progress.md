# Tiến độ — 00-repo-setup

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | pyproject + poe + config | ✅ | 2026-10-31 |  |
| 2 | Schema + Alembic trên SQLite | 🔄 |  |  |
| 3 | Oracle test qua VPN | ⬜ |  |  |
| 4 | Dash khung + theme + health | ⬜ |  |  |
| 5 | Worker khung + poe dev | ⬜ |  |  |
| 6 | Lint, typecheck, CI, cập nhật AGENTS.md mục Lệnh | ⬜ |  |  |

## Nhật ký
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
