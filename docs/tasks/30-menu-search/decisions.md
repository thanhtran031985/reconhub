# Quyết định — 30-menu-search

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-09 | Bỏ hẳn cách hiển thị badge "Mới" trong `shell.py`, không chỉ xoá cờ `IS_NEW` trong DB | Người dùng chốt: menu thêm sau này cũng không hiện "Mới" nữa | Thanh bên không còn nhãn "Mới" với mọi vai trò |
| 2026-11-09 | Ô tìm kiếm đặt trong khoảng trắng ở header, sau breadcrumb và trước badge môi trường (DEV/TEST/PROD) | Người dùng chốt vị trí bằng ảnh chụp header | Header có thêm ô tìm kiếm ở giữa |
| 2026-11-09 | Tìm theo tên menu, chuẩn hoá bỏ dấu + chữ thường cả 2 phía | Người dùng yêu cầu: gõ có dấu hay không dấu đều ra kết quả | Cần helper `_strip_accents` (NFKD + riêng Đ/đ) |
| 2026-11-09 | Danh sách tìm kiếm lấy từ cùng nguồn với thanh bên (`effective_menus`), chỉ hiện menu tài khoản được thấy | Đúng phân quyền hiện tại, không lộ menu không có quyền | Tìm kiếm tôn trọng phân quyền |
| 2026-11-09 | Dropdown kết quả dùng `dmc.Popover` (portal) | Không bị header 44px cắt như `div` tuyệt đối | Dùng portal như `dmc.Menu` đã kiểm chứng |
| 2026-11-09 | Một callback duy nhất xử lý gõ chữ + Enter + đổi trang | Tránh nhiều callback cùng ghi một Output (cần `allow_duplicate`) | Callback `handle_menu_search` có 3 kích hoạt |

## Câu hỏi còn mở
- Q0: Enter chuyển tới kết quả đầu tiên — có hay không?
- Q1: Giới hạn 8 kết quả + dòng "…và N kết quả khác" — có hay không?
- Q2: Chỉ khớp tên menu, hay khớp cả tên nhóm?
- Q3: Rộng ô tìm kiếm 320px — có hay rộng/hẹp hơn?
