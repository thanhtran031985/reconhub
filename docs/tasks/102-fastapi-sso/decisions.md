# Quyết định kỹ thuật: 102-fastapi-sso

## Quyết định 1: Dịch vụ FastAPI SSO độc lập (Native Python, không Docker)
- **Lý do**: Môi trường Windows on-premise không có Docker sẵn, mong muốn hệ thống gọn nhẹ, dễ bảo trì, hoàn toàn bằng Python.
- **Giải pháp**: Tạo package `sso_server/` chạy Uvicorn tại cổng 9000, có thể khởi động độc lập qua `uv run poe sso`.

## Quyết định 2: Chuyển màn hình sơ đồ SSO vào Menu Quản trị sau đăng nhập
- **Lý do**: ReconHub chặn các request Dash chưa đăng nhập ngoại trừ màn hình `/login`. Khi để link xem sơ đồ trên màn login, người dùng click vào bị chặn mã lỗi 401 UNAUTHORIZED dẫn đến màn hình trắng. Đồng thời sơ đồ kiến trúc hệ thống là thông tin nội bộ không nên hiển thị công khai.
- **Giải pháp**: Bỏ link xem sơ đồ trên trang `/login`, đăng ký menu `sso_flow` ("Kiến trúc SSO") trong nhóm `QUAN_TRI` có phân quyền bảo vệ `page_gate(ctx, "sso_flow")`.

## Quyết định 3: Bố cục Dual-Mode trên trang Login
- **Lý do**: Giữ giao diện đăng nhập quen thuộc, tránh nhầm lẫn khi người dùng quen bấm nút chính màu xanh.
- **Giải pháp**: Form đăng nhập mật khẩu cục bộ với nút "Đăng nhập" chính màu primary ở vị trí trên; nút "Đăng nhập qua SSO Doanh nghiệp" đặt ở dưới cùng sau đường phân cách "hoặc", chỉ hiển thị khi `SSO_ENABLED=true`.

## Quyết định 4: Sử dụng skill Archify cho sơ đồ tương tác
- **Lý do**: Skill Archify cung cấp sơ đồ phân hệ kiến trúc (`architecture` diagram) chuyên nghiệp, hỗ trợ dark/light mode, zoom, pan, export SVG/PNG chất lượng cao, trực quan hơn Mermaid.
- **Giải pháp**: Biên soạn file `candidate.json` cho kiến trúc 2 phân hệ (FastAPI SSO Server cổng 9000 và ReconHub Application cổng 8050), render ra `app/ui/assets/sso_flow_archify.html` và nhúng iframe vào trang `/sso-flow`.

## Quyết định 5: Switch Bật/Tắt SSO trên giao diện
- **Lý do**: Quản trị viên cần bật hoặc tắt chế độ SSO nhanh chóng mà không phải can thiệp file cấu hình qua terminal.
- **Giải pháp**: Thêm `dmc.Switch` trên thanh header trang `/sso-flow`. Callback xử lý cập nhật `settings.SSO_ENABLED` ngay trong bộ nhớ và đồng bộ xuống file `.env`.
