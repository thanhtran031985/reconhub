# 30-menu-search — Bỏ badge "Mới" ở menu thanh bên và thêm ô tìm kiếm menu ở header

- Ngày tạo: 2026-11-09
- Giai đoạn: GĐ3
- Phụ thuộc: 19, 20
- Nhánh git: feat/30-menu-search

## Mục tiêu
1. Bỏ hẳn badge "Mới" ở menu thanh bên: không còn hiển thị nhãn "Mới" sau tên các mục menu, kể cả với menu thêm sau này (không phải chỉ xoá cờ của các menu hiện tại).
2. Thêm ô tìm kiếm menu ở header, đặt trong khoảng trắng giữa breadcrumb và badge môi trường (DEV/TEST/PROD): gõ tên menu thì tìm ngay, gõ có dấu tiếng Việt hay không dấu đều ra kết quả, bo góc tròn kiểu Google Search; bấm vào kết quả thì chuyển tới trang đó.

## Phạm vi
- **Bỏ badge "Mới"**: chỉ bỏ cách hiển thị badge trong `app/ui/layout/shell.py` (`create_navbar`); cờ `IS_NEW` trong DB và logic đồng bộ menu (`menu_sync`) giữ nguyên; các màn khác dùng nhãn "Mới" (màn `/menus`, màn Vai trò) không đổi.
- **Ô tìm kiếm menu**:
  - Vị trí: header 44px, giữa breadcrumb (trái) và badge môi trường + nút đổi theme + User Menu (phải).
  - Kiểu dáng: `dmc.TextInput` bo tròn hoàn toàn (`radius="xl"`, kiểu Google Search), icon kính lúp bên trái, placeholder "Tìm kiếm menu...", rộng ~320px.
  - Tìm theo tên menu: chuẩn hoá bỏ dấu + chữ thường ở cả từ gõ và tên menu trước khi so khớp (gõ "doi soat" hay "đối soát" đều tìm được "Chạy đối soát").
  - Kết quả hiện trong dropdown dưới ô tìm kiếm (portal, không bị header cắt): mỗi kết quả có icon + tên menu + tên nhóm (chữ mờ); bấm vào thì chuyển tới trang đó; không khớp thì hiện "Không tìm thấy menu nào".
  - Chỉ tìm trong các menu mà tài khoản đang đăng nhập được thấy theo phân quyền (cùng danh sách với thanh bên).
  - Gõ Enter thì chuyển tới kết quả đầu tiên; chuyển trang xong thì ô tìm kiếm tự xoá trắng và đóng dropdown.

## Ngoài phạm vi
- Không đổi schema DB, không migration, không đổi logic phân quyền hay đồng bộ menu.
- Không tìm kiếm nội dung bên trong các trang (chỉ tìm tên menu).
- Không thêm phím tắt mở ô tìm kiếm (vd Ctrl+K).

## Thiết kế
- Mẫu menu thao tác 3 chấm: `app/ui/pages/report_admin.py` (đã dùng cho `/history` ở commit `4cf90bf`).
- Quy chuẩn giao diện: `.agents/rules/ui-dash.md` (Fluent Compact).

## Spec liên quan
- `docs/specs/11_menu_permission.md` §2.2 (đồng bộ menu, cờ IS_NEW) — chỉ tham chiếu, không đổi.

## Quyết định kiến trúc
- Danh sách menu cho tìm kiếm lấy từ cùng nguồn với thanh bên: `get_nav_items_for_menus(effective_menus(ctx), is_admin=is_admin(ctx))`, làm phẳng thành `dcc.Store` trong header để callback lọc không cần gọi lại DB.
- Dropdown kết quả dùng `dmc.Popover` (portal) thay vì `div` tuyệt đối, để không bị header 44px cắt.
- Một callback duy nhất xử lý cả 3 kích hoạt (gõ chữ, Enter, đổi trang) để tránh nhiều callback cùng ghi một Output.
- Hàm chuẩn hoá bỏ dấu đặt tại chỗ trong `shell.py` (`_strip_accents`, NFKD + riêng Đ/đ), không kéo dependency sang service batch.

## Các bước
### Bước 1 — Bỏ hẳn badge "Mới" ở menu thanh bên
- Làm: trong `create_navbar` (`app/ui/layout/shell.py`), bỏ khối `if item.get("is_new")` dựng `dmc.Badge("Mới", ...)`; nhãn menu luôn là chuỗi tên thuần. Cập nhật dòng docstring của `get_nav_items_for_menus` (nhãn "Mới" không còn hiển thị). Không đụng tới cờ `IS_NEW` trong DB hay `menu_sync`.
- Test viết trước: thêm test vào `tests/unit/test_menu_display.py` (hoặc file test shell): dựng navbar với menu có `is_new=True`, assert chuỗi render không chứa "Mới".
- Kiểm tra: `uv run poe test -- tests/unit/test_menu_display.py -q` xanh; chụp màn hình thanh bên không còn badge.

### Bước 2 — Ô tìm kiếm menu ở header
- Làm: trong `create_header` (`app/ui/layout/shell.py`), thêm ô tìm kiếm (`dmc.Popover` + `dmc.TextInput` bo tròn) vào giữa breadcrumb và badge môi trường; `dcc.Store` chứa danh sách menu đã làm phẳng; helper `_strip_accents`; callback `handle_menu_search` (gõ → lọc + mở dropdown; Enter → tới kết quả đầu; đổi trang → xoá + đóng).
- Test viết trước: unit test cho `_strip_accents` (có dấu/không dấu/Đ-đ) và cho hàm lọc (khớp không dấu, không khớp, giới hạn 8 kết quả); test callback đổi trang xoá ô tìm kiếm; kiểm chứng Playwright (gõ "doi soat" → thấy "Chạy đối soát", bấm → chuyển trang).
- Kiểm tra: `uv run poe test` xanh, `ruff check` + `ruff format` sạch, `mypy` sạch; chụp màn hình 1440×900 và 1366×768.

## Chấp nhận khi
- [ ] Thanh bên không còn badge "Mới" với mọi vai trò, kể cả ADMIN; menu thêm sau này cũng không hiện "Mới".
- [ ] Gõ "doi soat" và "đối soát" đều tìm được "Chạy đối soát"; bấm kết quả chuyển đúng trang; Enter tới kết quả đầu; chuyển trang xong ô tìm kiếm trống và dropdown đóng.
- [ ] Chỉ hiện menu mà tài khoản được thấy theo phân quyền.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh.

## Câu hỏi mở
- Q0: Enter chuyển tới kết quả đầu tiên — có hay không?
- Q1: Giới hạn 8 kết quả + dòng "…và N kết quả khác" — có hay không?
- Q2: Chỉ khớp tên menu, hay khớp cả tên nhóm (vd gõ "cấu hình" ra các menu nhóm Cấu hình)?
- Q3: Rộng ô tìm kiếm 320px — có hay rộng/hẹp hơn?
