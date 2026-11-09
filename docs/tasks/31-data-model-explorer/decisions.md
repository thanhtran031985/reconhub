# Quyết định — 31-data-model-explorer (DATA-MODEL-01)

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-09 | Hồ sơ task đặt ở `docs/tasks/31-data-model-explorer/`, giữ Task ID DATA-MODEL-01 trong task.md | Prompt muốn `tasks/DATA-MODEL-01/` nhưng repo dùng cấu trúc `docs/tasks/NN-slug/` (prompt §2: "nếu repository đang dùng cấu trúc khác thì đặt theo cấu trúc hiện tại"); số tiếp theo là 31; `tasks-dashboard` đọc bảng README theo số thứ tự | Nhánh `feat/31-data-model-explorer`, dòng 31 trong README |
| 2026-11-09 | Prototype `reconhub-er-diagram.html` chỉ là tham chiếu visual, KHÔNG phải source of truth | Prototype hiển thị 14 table đơn giản hoá (vd `APP_USER`) trong khi schema thật có 43 bảng (`RECON_USER`, …) trong `app/db/metadata.py` | Inspector phải tự phát hiện schema thật; test bước 1 bắt đủ 43 bảng |
| 2026-11-09 | Permission theo hệ thống menu hiện tại (task 19/20), KHÔNG tạo permission code `VIEW_DATA_MODEL` riêng | Prompt §12: không tự tạo permission nếu project dùng convention khác; repo dùng menu (`requires_menu`, `effective_menus`, cấp qua `/roles`) | Menu code `data_model`, service `@requires_menu("data_model")` |
| 2026-11-09 | Manifest/history đặt ở `docs/data-model/schema-manifest.json` và `schema-history.json` (generated, không sửa tay) | Theo prompt §7–§8; `docs/` là nơi chứa tài liệu sinh ra của repo | Inspector sinh 2 artifact này; CI diff manifest đã commit |
| 2026-11-09 | Command inspector là `uv run poe schema-introspect` (chưa tồn tại, sẽ thêm vào `pyproject.toml`) | Theo prompt §9; không trùng tên poe task hiện có | Entry CLI + poe task mới |
| 2026-11-09 | CI freshness thêm bước vào `.github/workflows/ci.yml` hiện có | Repo đã có CI (task 00); không tạo hệ CI mới | Bước CI generate manifest vào temp và diff |
| 2026-11-09 | Page là Dash page `/data-model` trong `app/ui/pages/data_model.py`, menu nhóm QUẢN TRỊ | Theo convention page (`dash.register_page`) và menu (`MenuDef` trong `app/ui/menus.py`); prompt §11/§13 | Route `/data-model`, menu code `data_model` |

| 2026-11-09 | Menu `data_model` hiện luôn sau khi ADMIN cấp quyền (không ẩn khỏi sidebar tới task sau) | Người dùng chốt lúc review task | Bước 3 khai báo menu và hiện ngay; khác cách `/menus` ở task 19 |
| 2026-11-09 | Manifest/history commit vào repo | Người dùng chốt lúc review task | CI freshness diff với manifest đã commit (bước 2); inspector không tự git add/commit/push |
| 2026-11-09 | Inspector chỉ đọc database của app (SQLite, `RECON_DB_URL`), không đọc các Oracle data source nghiệp vụ | Người dùng chốt "chỉ ER database SQLite" lúc review task | Phạm vi bước 1 là SQLite; kiểm chứng trên SQLite; Q3 coi như xong (không cần kiểm chứng Oracle cho task này) |

## Câu hỏi còn mở
- Q1: Domain mapping lấy từ đâu (tiền tố tên bảng / file cấu hình riêng / lai)? — đang chờ người dùng chọn sau khi nghe diễn giải thêm.
