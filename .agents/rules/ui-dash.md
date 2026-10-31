---
trigger: glob
globs: app/ui/**, tests/e2e/**
description: Quy tắc giao diện Dash Mantine và chuyển thiết kế từ designs/.
---

# Giao diện Dash Mantine

- designs/ CHỈ ĐỌC. Chỉ đọc `designs/components/<Tên>/README.md` và `preview.html` mà task liệt kê. Bảng ánh xạ thành phần → DMC ở `designs/README.md` mục "Ánh xạ sang Dash Mantine".
- Trước khi dùng component DMC, đọc trang của nó từ https://www.dash-mantine-components.com/llms (DMC 2.x, Mantine v8).
- Theme: `app/ui/theme.py` sinh bởi `uv run poe theme`. Không viết hex/px trong page; dùng `color="primary"`, `p="md"`, `radius="md"` hoặc biến CSS `assets/tokens.css`. Thiếu token: thêm vào tokens.json, chạy `uv run poe design-system` và `uv run poe theme`, báo cáo.
- Page: `dash.register_page` theo path ở `docs/specs/05_services_pages.md` mục 3. Mọi page (trừ /login) yêu cầu đăng nhập; page không đủ quyền chuyển tới /forbidden. ID component dạng `<page>-<khối>-<tên>`.
- Callback chỉ: lấy ctx, validate Pydantic, gọi service, dựng component. Việc > 2 giây giao cho worker.
- Bốn trạng thái: `dmc.Skeleton`; EmptyState (lý do + một hành động); `dmc.Alert` lỗi giữ dữ liệu cũ + Thử lại; có dữ liệu.
- Grid kết quả: `dag.AgGrid(rowModelType="infinite")`, columnDefs dựng từ metadata cột của service; ô lệch class `rh-diff`.
- Ngày giờ: `dmc.DateTimePicker(withSeconds=True, valueFormat="DD/MM/YYYY HH:mm:ss")`, giờ Việt Nam. Tiền `24.114.547.250`.
- Thao tác xóa (dữ liệu tạm, file SQLite cũ, khóa user): luôn qua `dmc.Modal` nêu rõ sẽ xóa gì, giữ lại gì; xóa hàng loạt yêu cầu gõ xác nhận.
- Kiểm tra giao diện bằng trình duyệt của Antigravity hoặc Playwright ở 1440×900 và 1366×768, chụp ảnh đính vào báo cáo bước.
