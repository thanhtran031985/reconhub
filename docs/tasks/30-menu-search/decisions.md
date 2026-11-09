# Quyết định — 30-menu-search

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-09 | Bỏ hẳn cách hiển thị badge "Mới" trong `shell.py`, không chỉ xoá cờ `IS_NEW` trong DB | Người dùng chốt: menu thêm sau này cũng không hiện "Mới" nữa | Thanh bên không còn nhãn "Mới" với mọi vai trò |
| 2026-11-09 | Ô tìm kiếm đặt trong khoảng trắng ở header, sau breadcrumb và trước badge môi trường (DEV/TEST/PROD) | Người dùng chốt vị trí bằng ảnh chụp header | Header có thêm ô tìm kiếm ở giữa |
| 2026-11-09 | Tìm theo tên menu, chuẩn hoá bỏ dấu + chữ thường cả 2 phía | Người dùng yêu cầu: gõ có dấu hay không dấu đều ra kết quả | Cần helper `_strip_accents` (NFKD + riêng Đ/đ) |
| 2026-11-09 | Danh sách tìm kiếm lấy từ cùng nguồn với thanh bên (`effective_menus`), chỉ hiện menu tài khoản được thấy | Đúng phân quyền hiện tại, không lộ menu không có quyền | Tìm kiếm tôn trọng phân quyền |
| 2026-11-09 | Dropdown kết quả dùng `dmc.Paper` định vị tuyệt đối trong `dmc.Box` relative (không dùng `dmc.Popover` như plan ban đầu) | Kiểm chứng Playwright: không bị header 44px cắt, đơn giản hơn, không cần portal | Dropdown phủ lên nội dung bên dưới header |
| 2026-11-09 | Một callback duy nhất xử lý gõ chữ + Enter + đổi trang | Tránh nhiều callback cùng ghi một Output (cần `allow_duplicate`) | Callback `handle_menu_search` có 3 kích hoạt |
| 2026-11-09 | Phím mũi tên chọn menu bằng file JS riêng trong `app/ui/assets/` (listener `keydown` ở tầng document, capture phase), tô sáng bằng class CSS, không đổi code Python | `TextInput` của Dash không có sẵn phím tắt di chuyển; trạng thái tô sáng suy ra từ DOM nên không cần store riêng; capture phase chạy trước listener của React/Dash nên chặn được `n_submit` khi Enter đã tô sáng | File `menu_search_keys.js` + rule CSS `a.menu-search-highlight` |

## Câu hỏi còn mở
- Q0: Enter chuyển tới kết quả đầu tiên — có hay không?
- Q1: Giới hạn 8 kết quả + dòng "…và N kết quả khác" — có hay không?
- Q2: Chỉ khớp tên menu, hay khớp cả tên nhóm?
- Q3: Rộng ô tìm kiếm 320px — có hay rộng/hẹp hơn?
