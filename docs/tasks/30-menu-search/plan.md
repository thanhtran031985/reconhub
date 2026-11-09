# Kế hoạch — 30-menu-search

## Bối cảnh
- Nhánh: `feat/30-menu-search`, rẽ từ `4cf90bf` (đỉnh `feat/29-reporting-fluent-ui`, đã gồm patch dashboard `9714cc3` + patch layout `/history` `4cf90bf`).
- Vấn đề 1: thanh bên hiện badge xanh "Mới" sau tên mọi mục menu (chỉ ADMIN thấy). Badge bật vì các menu được đồng bộ vào DB với cờ `IS_NEW='Y'` và chưa được đánh dấu đã xem. Người dùng muốn bỏ hẳn cách hiển thị này, menu thêm sau này cũng không hiện "Mới".
- Vấn đề 2: chưa có cách tìm nhanh menu — người dùng muốn ô tìm kiếm ở header, trong khoảng trắng giữa breadcrumb và badge môi trường (DEV/TEST/PROD), bo tròn kiểu Google Search, gõ có dấu hay không dấu đều tìm được tên menu.

## Cách làm

### Bước 1 — Bỏ badge "Mới" (nhỏ, làm trước)
- File duy nhất: `app/ui/layout/shell.py`, hàm `create_navbar`.
- Xoá khối `if item.get("is_new"):` dựng `dmc.Group` chứa `dmc.Badge("Mới", ...)`; `label_node` luôn là chuỗi tên menu thuần.
- Cập nhật 1 dòng docstring của `get_nav_items_for_menus` (nhãn "Mới" không còn hiển thị).
- Không đụng: cờ `IS_NEW` trong DB, `menu_sync`, màn `/menus`, màn Vai trò, và dict `is_new` trong nav item (các test `test_menu_display.py` vẫn assert dữ liệu đó).
- Test viết trước (đỏ → xanh): thêm test dựng navbar với menu có `is_new=True`, assert chuỗi render không chứa "Mới".
- Kiểm tra: `uv run poe test -- tests/unit/test_menu_display.py -q` xanh; chụp thanh bên.

### Bước 2 — Ô tìm kiếm menu ở header
- File chính: `app/ui/layout/shell.py`, hàm `create_header` + 1 callback mới ở cuối file.
- Component: `dmc.Popover` (portal, không bị header 44px cắt) bọc `dmc.TextInput` (`radius="xl"`, `leftSection` icon kính lúp, placeholder "Tìm kiếm menu...", rộng ~320px) làm target; `dmc.PopoverDropdown` chứa danh sách kết quả.
- Dữ liệu: trong `create_header` (đã có `ctx`), gọi `get_nav_items_for_menus(effective_menus(ctx), is_admin=is_admin(ctx))` — cùng nguồn với thanh bên — làm phẳng thành list `{label, href, icon, group}` rồi đưa vào `dcc.Store(id="app-menu-search-store")` trong header. Callback lọc chỉ đọc store, không gọi lại DB.
- Chuẩn hoá: helper `_strip_accents` tại chỗ trong `shell.py` (NFKD + riêng Đ/đ + lower); khớp khi chuỗi gõ đã chuẩn hoá là chuỗi con của tên menu đã chuẩn hoá.
- Callback duy nhất `handle_menu_search` (tránh nhiều callback cùng ghi một Output):
  - Input: giá trị ô tìm kiếm, `n_submit` (Enter), `app-location` pathname. State: dữ liệu store.
  - Output: children dropdown kết quả, `opened` của Popover, giá trị ô tìm kiếm, `href` của `app-location`.
  - Gõ chữ → lọc, mở dropdown (có kết quả hoặc dòng "Không tìm thấy menu nào"); tối đa 8 kết quả + dòng "…và N kết quả khác" nếu thừa.
  - Enter → chuyển tới kết quả đầu tiên (set `href`), xoá ô tìm kiếm, đóng dropdown.
  - Đổi trang (pathname đổi, kể cả khi bấm vào kết quả) → xoá ô tìm kiếm, đóng dropdown.
- Test viết trước (đỏ → xanh): unit test `_strip_accents` (có dấu/không dấu/Đ-đ/chữ hoa); unit test hàm lọc (khớp không dấu, không khớp, giới hạn 8); test callback đổi trang xoá ô tìm kiếm.
- Kiểm tra: `uv run poe test` xanh, `ruff check` + `ruff format` sạch, `mypy` sạch; kiểm chứng Playwright trên server thử (gõ "doi soat" → thấy "Chạy đối soát", bấm → chuyển trang; gõ "xyz" → "Không tìm thấy menu nào"); chụp màn hình 1440×900 và 1366×768.

## Thứ tự commit (mỗi bước 1 commit)
1. `30-menu-search: step 1 — drop "Mới" badge from sidebar`
2. `30-menu-search: step 2 — header menu search`

## Kiểm chứng cuối
- `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh (full suite).
- Chụp màn hình cho người dùng xem trước rồi mới xuất patch `4cf90bf..HEAD` (không cần db-migrate, chỉ khởi động lại app sau khi áp).

## Rủi ro
- `dmc.Popover` bọc `TextInput`: nếu target không nhận focus đúng, đổi sang `div` tuyệt đối có kiểm soát `zIndex`. Đã chọn Popover trước vì nó dùng portal như `dmc.Menu` (đã kiểm chứng ở `/history`).
- `render_app_shell` dựng lại header mỗi lần đổi trang nên store menu luôn mới theo quyền hiện tại; callback tìm kiếm không cần tự làm mới store.
