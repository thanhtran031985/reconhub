# Kế hoạch — 19-menu-permission

_Implementation Plan đã duyệt nguyên văn ngày 05/11/2026. Người dùng duyệt plan và làm theo đề xuất cho Q0–Q11 (xem decisions.md). Task 18 tạm bỏ qua; Q10 chốt theo hướng 1: các run cũ giữ nguyên CREATED_BY='admin', chỉ ADMIN thấy, không gán lại chủ sở hữu._

## Bước 1 — Schema và migration
- Làm: tạo `RECON_MENU_GROUP`, `RECON_MENU`, `RECON_ROLE`, `RECON_ROLE_MENU`; đổi `RECON_USER_ROLE` sang `ROLE_ID` (+ `ASSIGNED_BY`, `ASSIGNED_AT`), xử lý `ORG_SCOPE` theo quyết định ở trên; seed 4 vai trò + menu theo seed 11a mục 7 (đã đối chiếu bảng 1, 2); thêm `PERM_REVISION`, `MENU_SYNC_LOCK` vào `RECON_APP_SETTING`; test viết trước `test_perm_migration.py` (upgrade/downgrade, user cũ giữ đúng menu tương đương v4 trừ 2 thay đổi ở Q4, downgrade có vai trò tự tạo báo lỗi rõ). Kiểm tra: `uv run poe test`.

## Bước 2 — Khai báo menu và đồng bộ
- Làm: tạo `app/ui/menus.py` (MENUS, GROUPS theo bảng 1, kèm `menu_admin`, `batch_run`, `batch_def` nhưng `menu_admin` tạm ẩn khỏi thanh bên theo Q7, batch chưa có page nên chưa hiện link); tạo `app/services/menu_sync.py` (thêm mới IS_NEW, đổi SOURCE_*/PATH không ghi đè DISPLAY_*, gỡ khỏi code → IS_REMOVED, xuất hiện lại khôi phục cấu hình, khóa `MENU_SYNC_LOCK`, tăng PERM_REVISION + audit actor system khi đổi); test viết trước `test_menu_sync.py` (gồm 2 process khởi động cùng lúc). Kiểm tra: `uv run poe test`.

## Bước 3 — Tính quyền và kiểm tra
- Làm: tạo `app/services/perm.py` (`effective_menus`, `is_admin`, `@requires_menu` hỗ trợ `any_of`, `require_admin`, `owner_filter`, cache theo `(user_id, PERM_REVISION)`, đọc revision tối đa 1 lần/giây); gắn `menu_code` cho mọi page theo bảng 1 (page không có quyền → `/forbidden`, menu đang ẩn → trang "Chức năng tạm ngưng" cho vai trò thường, ADMIN vẫn vào); thay `require_role` trong service theo bảng 2 (giữ rào chắn ghi/xóa template và require_admin cho các hàm ở cột cuối); test viết trước `test_perm_effective.py`, `test_perm_registry.py` (quét page + service có ctx, thiếu menu_code → đỏ, với danh sách miễn trừ Q6 + helper thuần). Kiểm tra: `uv run poe test`.

## Bước 4 — Phạm vi dữ liệu
- Làm: gắn `owner_filter` cho mọi đường ở bảng 3 (run, dashboard, issue, route Flask; batch để lại stub/test skip có ghi chú cho tới khi task 18 xong, nếu Q1 chốt làm ngay); test viết trước `test_owner_scope.py` (B dùng ID của A ở mọi đường → NOT_FOUND, ADMIN thấy hết, chạy lại tạo run mới đúng `CREATED_BY`). Kiểm tra: `uv run poe test`.

## Bước 5 — Service vai trò
- Làm: tạo `app/services/role.py` (`list`, `get`, `create`, `clone`, `update`, `delete`, `users_of`, `effective_of_user`) với rào chắn ADMIN, LAST_ADMIN, ROLE_IN_USE, ROW_VERSION, audit kèm menu trước/sau; màn `/users` chuyển sang chọn vai trò từ `RECON_ROLE` (thay checkbox ADMIN/TO/OP/VI cố định). Test viết trước `test_role_service.py`. Kiểm tra: `uv run poe test`.

## Bước 6 — UI vai trò và thanh bên
- Làm: tạo `app/ui/pages/roles.py` theo spec 11 mục 7.1 (bỏ bảng "Phạm vi dữ liệu và thao tác đặc biệt", thay bằng dòng ghi chú; checkbox menu từ `RECON_MENU` kèm nhãn Mới/Đang ẩn; tab Quyền thực tế + Mô phỏng; hộp thoại lưu liệt kê menu thêm/bỏ + số người ảnh hưởng) — chỉ làm được đúng preview nếu Q2 có file Screen14, nếu không thì làm theo mô tả này; thanh bên đọc `effective_menus`, `dcc.Interval` 5 giây kiểm revision, đổi revision thì dựng lại; trang `/forbidden` đã có, bổ sung trang "Chức năng tạm ngưng" (lý do ẩn lấy từ `HIDDEN_REASON`, task 20 mới có màn nhập lý do nên ở task 19 lý do này chỉ có khi đồng bộ hoặc seed). Test viết trước: e2e `test_roles.py`. Kiểm tra: `uv run poe e2e`.

## Bước 7 — Cập nhật task cũ và hồi quy
- Làm: thay `require_role` còn sót trong page (`data_sources`, `users`, `lookups`, `new_run`, `template_wizard`, `history`, `issues`, shell) sang `requires_menu`/`require_admin`/`is_admin`; cập nhật `docs/tasks/README.md` (thêm 18, 19, 20 — hiện README mới tới task 17), `USER_GUIDE`, thứ tự chép chuyển Oracle theo spec 11 mục 10 (`MENU_GROUP` → `MENU` → `ROLE` → `ROLE_MENU` trước `USER_ROLE`, thuộc CONFIG_ONLY); chạy toàn bộ test + test-oracle qua VPN (ghi rõ nếu chưa chạy được). Kiểm tra: `uv run poe test`, `uv run poe test-oracle`, `uv run poe typecheck`, `lint`, `e2e`.

## Rủi ro chính
- Q1 (batch chưa có code) làm test T19-05-03, T19-00-01 (2 lần chạy bộ) không chạy được mà chỉ viết dạng skip có ghi chú; Q5 (đọc/ghi template) nếu bạn chốt bỏ rào chắn thì bước 3 phải đổi test template tương ứng; hiệu lực ≤ 5 giây phụ thuộc `dcc.Interval` ở thanh bên + cache revision, cần test e2e 2 trình duyệt như checklist T19-07-01.
- Không cài package mới.
