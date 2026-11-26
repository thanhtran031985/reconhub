# Quyết định — 107-model-studio-ui

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-26 | Giữ `dmc.AppShell` sidebar dọc thay cho top-tabbar trên ảnh wireframe | Quy tắc `.agents/rules/ui-dash.md` yêu cầu thống nhất AppShell cho mọi page | Nút chuyển sang Report Studio đặt ở `page_header` |
| 2026-11-26 | Dùng HTML Entity Cards + lớp SVG nối dây vừa khung canvas + JS clientside `set_props` | Tránh full-page SVG gây page-scroll (bài học từ Task 31) và tránh round-trip server khi kéo chuột | Tạo `app/ui/assets/semantic_model_canvas.js` |
| 2026-11-26 | Bổ sung form `+ Tạo quan hệ` song song thao tác kéo cột-sang-cột | Đáp ứng Accessibility bàn phím và thuận tiện cho bảng Oracle nhiều cột | Thêm nút/modal gọn trong Explorer & Canvas toolbar |
| 2026-11-26 | Mobile (`390×844`) chỉ mở chế độ xem tóm tắt + thông báo thiết kế trên desktop | Kéo thả sơ đồ quan hệ và 3 panel không khả thi trên màn hình 390px | Đáp ứng mục §83 của prompt gốc |

| 2026-11-26 | Dùng vanilla Pointer Events JS thuần trong `semantic_model_canvas.js` | Đồng bộ với `data_model_canvas.js`, đủ nhẹ/mượt 60fps và không phát sinh dependency JS/Python ngoài | Không cần nạp `interactjs` |

## Câu hỏi còn mở
- Không có (người dùng đã duyệt kế hoạch và chốt dùng vanilla JS thuần).
