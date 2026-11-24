# Quyết định — 101-interactive-grid

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-23 | Sử dụng Tabulator JS thuần nạp qua assets thay vì dùng wrapper thư viện ngoài | Kiểm soát trực tiếp 100% DOM, tránh các lỗi render và dễ dàng tùy biến CSS Fluent Compact chính xác theo design tokens. | Giữ kiến trúc Dash chuẩn, nạp script tĩnh trong `app/ui/assets/`. |
| 2026-11-23 | Tắt `persistence` mặc định của Tabulator, tự lưu cấu hình View vào `localStorage` | Bật `persistence: { columns: true }` khiến Tabulator serialize column definitions thành JSON, làm mất định nghĩa hàm `headerFilter: "input"` dẫn đến lỗi crash console. Tự lưu layout `{ field, width }` giúp tránh hoàn toàn lỗi này. | Khắc phục triệt để lỗi `Filter Error: No such editor found`. |
| 2026-11-23 | Kích hoạt `resizableColumnFit: true`, bỏ gán `minWidth = it.width`, dùng `widthGrow: 3` cho cột tên | Cho phép người dùng kéo thu nhỏ cột tùy ý (minWidth 80px), đồng thời tự động co dãn dãn kín 100% màn hình khi đóng/mở sidebar. | Tránh lỗi bảng bị hở khoảng trống màu trắng bên phải khi ẩn menu. |
| 2026-11-23 | Thay thế hoàn toàn popup trình duyệt (`prompt`, `confirm`, `alert`) bằng `dmc.Modal` | Popup mặc định của trình duyệt phá vỡ trải nghiệm Fluent UI, gây khó chịu cho người dùng và không đồng bộ giao diện. | Bổ sung 2 modal chuẩn Fluent trong `batch_defs.py`. |
| 2026-11-23 | Bỏ thanh tìm kiếm/lọc bên trên bảng (`cmd_bar`) | Header filters tích hợp trực tiếp trên từng cột của Interactive Grid đã đáp ứng đầy đủ và trực quan hơn, bỏ thanh cũ giúp tiết kiệm diện tích màn hình. | Giao diện gọn gàng, đúng chuẩn Oracle APEX Interactive Grid. |

## Câu hỏi còn mở
- Không còn câu hỏi mở.
