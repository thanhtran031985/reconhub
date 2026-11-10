# Quyết định — Task 45

- Main height `100vh` thay vì `calc(100vh - 44px)`: header fixed nên
  main bắt đầu từ y=0; padding-top 44 của Mantine vẫn chừa chỗ cho header.
  Các trang con dùng `calc(100vh - 48px)` được thêm 44px không gian.
- Bỏ Input pathname khỏi `handle_menu_search`: `render_app_shell` dựng
  lại toàn bộ header mỗi lần đổi trang nên ô tìm kiếm luôn về `value=""`
  và dropdown ẩn — không mất hành vi xóa khi đổi trang.
- `value=None` → `""`/`[]` chỉ ở `render_param_control`: an toàn vì
  `resolve_param_values` coi `""`/`[]` là thiếu giá trị như `None`.
- Không sửa `issues.py`: service chỉ ghi REASON_CODE khi khác None nên
  đổi sang `""` sẽ ghi đè `""` xuống DB — đổi hành vi lưu, để sửa riêng.
- Cảnh báo proxy chặn CDN iconify (ERR_TUNNEL_CONNECTION_FAILED) là do
  môi trường, không phải code — không sửa trong task này.
