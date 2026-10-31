---
name: ra-soat-ui
description: So sánh các màn đã code với designs/components ở 2 kích thước, 4 trạng thái và chế độ tối. Dùng khi người dùng nói "rà soát giao diện", "so với thiết kế" hoặc gọi /ra-soat-ui.
---

# Rà soát giao diện

1. `uv run poe dev`, đăng nhập bằng user mẫu từ `uv run poe db-seed`.
2. Với từng màn đã làm: mở bằng trình duyệt của Antigravity (hoặc Playwright) ở 1440×900 và 1366×768; xem 4 trạng thái bằng service giả của e2e; xem chế độ tối.
3. Mở `designs/components/<ScreenNN>/preview.html` cùng kích thước, trạng thái.
4. Chụp ảnh vào `tests/e2e/__screens__/`, lập bảng: Màn | Trạng thái | Khác biệt | Mức | Đề xuất sửa.
5. Không sửa code; chờ người dùng chọn mục cần sửa.
