# Implementation Plan — 20-menu-admin (đã duyệt 06/11/2026 10:41)

Người dùng nhắn "Duyệt plan, làm theo đề xuất". Chép nguyên văn vào
`docs/tasks/20-menu-admin/plan.md` sau khi tạo nhánh `feat/20-menu-admin`.

## Mục tiêu

Màn `/menus` cho Admin chỉnh cách hiển thị menu mà không sửa code: đổi tên
hiển thị, đổi nhóm, đổi thứ tự menu và nhóm, tạm ẩn menu khỏi mọi vai trò
(kèm lý do), khôi phục mặc định, đánh dấu đã xem menu mới. Không tạo menu,
không sửa đường dẫn.

## Điểm xuất phát (đã có từ task 19)

- Schema đủ (RECON_MENU/GROUP với DISPLAY_*, IS_HIDDEN/HIDDEN_REASON,
  IS_NEW, IS_REMOVED, IS_HIDEABLE, ROW_VERSION — migration 0003): không cần
  migration mới.
- Đồng bộ code giữ DISPLAY_*, đánh dấu menu gỡ khỏi code, khôi phục khi xuất
  hiện lại, IS_NEW cho menu mới; `list_menu_tree` trả cây theo hiển thị.
- `effective_menus` trừ menu ẩn với vai trò thường, ADMIN có tất cả chưa gỡ;
  `requires_menu` trả MENU_HIDDEN (ưu tiên MENU_REMOVED > MENU_HIDDEN >
  FORBIDDEN); `page_gate` trả `/suspended`; `menu_state`,
  `bump_perm_revision`, cache 5 giây đã có.
- Trang "Chức năng tạm ngưng" (`/suspended`) đã có, hiện lý do.
- Sidebar đã dùng DISPLAY_LABEL nhưng vẫn lấy nhóm/thứ tự từ code, bỏ qua
  menu ẩn với mọi người (kể cả ADMIN); `menu_admin` còn trong
  `_SIDEBAR_SKIP_CODES`.
- `/roles` đã dùng `list_menu_tree` (tên/nhóm/thứ tự hiển thị), checkbox có
  nhãn "Đang ẩn" — nhãn "Mới" đã bỏ ở patch bố cục vì lúc đó mọi menu đều mới.

## Các bước

### Bước 1 — Service và quy tắc

- Làm: `app/services/menu_admin.py` — `list_tree`, `save` (một lần cho mọi
  thay đổi, ROW_VERSION), `reset` (một menu/tất cả), `mark_seen`,
  `preview_sidebar`; kiểm hợp lệ, chặn menu bắt buộc, audit, PERM_REVISION.
- Test viết trước: `tests/unit/test_menu_admin_service.py`.
- Kiểm tra: `uv run poe test`.

### Bước 2 — Áp dụng ẩn menu

- Làm: page/service trả MENU_HIDDEN (đã có ở `perm`, rà soát lại); trang
  "Chức năng tạm ngưng" (đã có); ADMIN vẫn vào; sidebar ADMIN hiện menu ẩn
  với nhãn "Đang ẩn"; trang chủ chuyển khi dashboard bị ẩn (xem Q2).
- Test viết trước: `tests/unit/test_menu_hidden.py` (bổ sung phần còn thiếu).
- Kiểm tra: `uv run poe test`.

### Bước 3 — Hiển thị theo DISPLAY_*

- Làm: thanh bên, màn Vai trò dùng tên/nhóm/thứ tự hiển thị từ DB; khôi phục
  nhãn "Mới" ở `/roles` và thanh bên ADMIN; khôi phục mặc định; sync không
  ghi đè (đã có — test lại).
- Test viết trước: `tests/unit/test_menu_display.py`.
- Kiểm tra: `uv run poe test`.

### Bước 4 — UI Danh sách menu

- Làm: `app/ui/pages/menus.py` theo Screen15: bảng nhóm+menu, lọc, tìm, xem
  trước thanh bên, hộp thoại ẩn và lưu; đăng ký page với
  `MENU_CODE = "menu_admin"`; bỏ `menu_admin` khỏi `_SIDEBAR_SKIP_CODES`.
- Test viết trước: e2e `tests/e2e/test_menus.py`.
- Kiểm tra: `uv run poe e2e`.

### Bước 5 — Hồi quy

- Làm: toàn bộ test; menu mới từ code vẫn tự xuất hiện.
- Test viết trước: toàn bộ test.
- Kiểm tra: `uv run poe test`.

## Quyết định đã chốt (Q0–Q8)

- Q0: nhánh mới `feat/20-menu-admin`, tạo từ đầu nhánh 19 sau khi đã có patch
  bố cục `/roles`. Người dùng áp patch bố cục + push trước, trợ lý đồng bộ
  clone về hash mới rồi mới tạo nhánh.
- Q1: nhãn "Mới" trên 13 menu seed (sau migration tất cả đều IS_NEW='Y'):
  thêm nút "Đã xem tất cả" ở `/menus` để Admin bấm một lần cho sạch; giữ
  nguyên cơ chế tự bỏ nhãn khi bật menu cho vai trò hoặc bấm "Đã xem" từng
  menu. Không migration xóa cờ.
- Q2: ẩn dashboard → riêng trang chủ ("/") khi gate trả `/suspended` thì
  chuyển tới menu đầu tiên người dùng có, thay vì trang "Chức năng tạm
  ngưng". Các page khác vẫn về `/suspended`.
- Q3: khóa lạc quan khi lưu — payload lưu mang theo `row_version` từng dòng
  bị đổi; service kiểm tra từng dòng, sai thì báo STALE_DATA, không ghi đè
  dòng nào.
- Q4: bảng dùng `dmc.Table` như các bảng khác thay vì AgGrid (dưới 50 dòng,
  ô sửa trong từng dòng đơn giản hơn).
- Q5: nút "Mô phỏng đồng bộ từ code" chỉ có trong prototype, không làm.
- Q6: cảnh báo rời trang khi chưa lưu (T20-03-03, ưu tiên Thấp) — làm bằng
  clientside callback beforeunload nếu đơn giản, không ổn định thì bỏ qua
  (ghi decisions.md).
- Q7: tự bỏ nhãn "Mới" — khi lưu vai trò có tick menu mới thì `role.update`
  tự đặt IS_NEW='N' cho menu đó trong cùng transaction.
- Q8: cột "Vai trò bật" đếm vai trò đang dùng (IS_ACTIVE='Y') có menu đó.

## Quy trình làm

Theo AGENTS.md: làm đúng thứ tự các bước; viết test hành vi trước (thấy đỏ)
rồi code cho xanh; sau MỖI bước chạy phần "Kiểm tra", cập nhật progress.md,
chạy tasks-dashboard, báo cáo ngắn, đề xuất commit, DỪNG chờ "continue".
Chỉ commit khi được đồng ý. Khác task.md/spec/thiết kế: ghi decisions.md.
Trước khi báo xong: `uv run poe typecheck`, `lint`, `test`, `e2e` xanh.
