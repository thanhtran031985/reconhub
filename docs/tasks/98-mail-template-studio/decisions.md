# Quyết định kỹ thuật — 98-mail-template-studio

## D-01: Kiến trúc Lưu trữ: Design JSON vs Rendered HTML
- **Bối cảnh**: Hệ thống cũ (Task 97) lưu trực tiếp chuỗi HTML (`BODY_HTML`). Nhưng khi người dùng muốn mở lại để kéo thả, sửa đổi từng component riêng lẻ thì không thể parse ngược từ HTML tùy biến một cách tin cậy.
- **Quyết định**: Nguồn sự thật duy nhất (Single Source of Truth) là `DESIGN_JSON`. Cột `RENDERED_HTML` và `PLAIN_TEXT` chỉ đóng vai trò snapshot/cache do Renderer backend sinh ra tại thời điểm Activate hoặc Save.

## D-02: Cơ chế Renderer: Table-based lồng nhau cho Email Client
- **Bối cảnh**: Các trình đọc email doanh nghiệp phổ biến (đặc biệt Microsoft Outlook Desktop dùng engine Word để render) không hỗ trợ CSS Grid, Flexbox hay modern layout.
- **Quyết định**: Backend Renderer dịch `DESIGN_JSON` thành cấu trúc HTML thuần sử dụng các thẻ `<table>`, `<tr>`, `<td>` với thuộc tính inline style an toàn, đảm bảo hiển thị đồng nhất trên Outlook, Gmail, Apple Mail.

## D-03: Kéo thả và tương tác Canvas trong Dash
- **Bối cảnh**: Kéo thả component liên tục nếu gửi request server round-trip về Dash sẽ bị giật lag và độ trễ cao.
- **Quyết định**: Canvas kéo thả và sắp xếp component được tối ưu hóa bằng clientside interactions / custom iframe sandbox giao tiếp state qua window postMessage / Dash Store để đảm bảo trải nghiệm mượt mà 60fps đúng theo prototype `preview.html`.

## D-04: Dynamic Token Introspection theo Page/Table
- **Bối cảnh**: Người dùng không muốn bị bó hẹp trong các biến token tĩnh được khai báo cứng trong mã nguồn backend cho từng event.
- **Quyết định**: Xây dựng module `mail_token_inspector.py` tự động quét metadata bảng dữ liệu theo `MENU_CODE` / `PAGE_CODE` tương ứng của màn hình gửi thư (ví dụ `/users` -> `RECON_USER`), tự động sinh danh sách Token có tiền tố (`user.username`) và không tiền tố (`username`), loại bỏ các cột nhạy cảm nội bộ (`PASSWORD_HASH`, `SESSION_VERSION`), kết hợp cùng System Tokens (`actor.name`, `links.login`, `links.page`...).

## D-05: Tích hợp sự kiện USER_CREATED và Export Danh sách Người dùng
- **Bối cảnh**: Cần tự động gửi thư chào mừng tài khoản mới khi tạo người dùng trên `/users` và hỗ trợ xuất danh sách người dùng kèm gửi email.
- **Quyết định**: Đăng ký sự kiện `USER_CREATED` và `USER_LIST_EXPORT` vào Registry; tích hợp hook gửi email an toàn chịu lỗi (fault-tolerant) trong `create_user` và xây dựng service `user_export.py`.

## D-06: Xác thực Token linh hoạt theo Page, Case-Insensitive và Nâng cấp Nút bấm (Button)
- **Bối cảnh**:
  1. Khi người dùng chọn trang gửi thư `/users`, template ID 5 ("Tạo mới user") vẫn mang `EVENT_CODE='GENERAL_EXPORT'` do chưa được lưu đồng bộ trang, dẫn đến lỗi kích hoạt *"Khối #2 (text) chứa biến không thuộc sự kiện: user.username; Khối #5 (text) chứa biến không thuộc sự kiện: user.username, user.temp_password"*.
  2. Danh mục token hệ thống bị đẩy xuống dưới đáy panel trái không cuộn tới được, và huy hiệu bị ép thành chữ IN HOA (`USER.USERNAME`).
  3. Khối Nút liên kết (Button) khi đặt nền trắng `#ffffff` bị chìm thành đoạn văn bản thường trên canvas, thiếu tùy chọn bo tròn/vuông vắn và độ rộng.
- **Quyết định**:
  1. `mail_renderer.py` & `mail_token_inspector.py`: Bổ sung `get_all_valid_tokens_set`, cho phép `validate_design` nhận `menu_code`, kiểm tra hợp lệ mọi token của trang và hệ thống không phân biệt hoa thường (`case-insensitive`).
  2. `mail_template_studio.py` (service): `save_draft_version` nhận `page_code`, tự động cập nhật `MENU_CODE` và chuyển `EVENT_CODE` tương ứng (`USER_CREATED`).
  3. UI Panel Trái: Tổ chức Tokens thành 2 tab (`Trường bảng` vs `Hệ thống`) với vùng cuộn `maxHeight: 240px`, đặt `tt="none"` trên `dmc.Badge` giữ nguyên chữ thường `{{user.username}}`.
  4. Nút liên kết (Button): Bổ sung thuộc tính `button_shape` (`round` 24px, `rounded` 6px, `square` 0px), `button_width` (`auto` co giãn theo chữ vs `full` toàn hàng), tự động thêm viền `1px solid #cbd5e1` và đổ bóng nhẹ khi nền trắng để nút luôn hiển thị trực quan đúng chuẩn nút bấm trên cả Canvas và Email client.

## D-07: Tối ưu UI Studio, Loại bỏ Hardcode Component và Cấu hình Base URL Hệ thống
- **Bối cảnh**:
  1. Thư viện 11 component ở panel trái chiếm nhiều diện tích đứng khiến danh sách Tokens bị đẩy xuống dưới.
  2. Khi người dùng đổi màu chữ và màu nền cho Nút liên kết (Button), màu lại bị ăn vào cả khung Paper bọc ngoài block thay vì áp vào chính nút bấm.
  3. Các component Cảnh báo (Alert), Chỉ số (KPI), Bảng dữ liệu (Table) có một số giá trị hardcode (màu viền cam cố định, nhãn KPI cố định, dataset cố định `batch.items`).
  4. Token `links.login` khi gửi email bị lỗi `http:///login` do thiếu host/domain khi chạy nền không có HTTP request context.
- **Quyết định**:
  1. **Thư viện component**: Chia lưới 3 component trên 1 hàng (`cols=3`, padding `6px 4px`), chiều cao paper bên trái tính động theo `calc(100vh - 145px)` giúp danh mục Tokens và Tabs hiển thị trọn vẹn, có thanh cuộn riêng biệt.
  2. **Nút liên kết (Button)**: Tách biệt hoàn toàn `bg` và `color` của Button với khung chứa Canvas (khung chứa card luôn giữ `#ffffff`). Nhãn form thuộc tính chuyển thành "Màu chữ nút" và "Màu nền nút" khi đang chọn block button. Giá trị mặc định khi tạo mới nút là nền xanh `#2563eb` và chữ trắng `#ffffff`.
  3. **Loại bỏ hardcode component**:
     - *Alert*: Đọc động `border_color` và `bg` từ cấu hình block.
     - *KPI*: Đọc động nhãn `kpi1_label`, `kpi2_label`, `kpi3_label` và fallback đa nguồn số liệu.
     - *Table*: Đọc động danh sách từ `items`, `rows`, `data`, `files_list`... và tự động dịch tên cột tiếng Việt qua `COLUMN_LABELS`.
  4. **Base URL hệ thống (APP_BASE_URL)**:
     - Thêm trường cấu hình URL hệ thống trong Cài đặt SMTP (mặc định `http://127.0.0.1:8050`).
     - Hàm `build_app_url(path)` tự động sinh link tuyệt đối lúc gửi email (`http://127.0.0.1:8050/login`), compiler email tự động bắt và chuẩn hóa các relative link `/...` thành link an toàn.

## D-08: Nâng cấp Dynamic Columns cho Bảng dữ liệu (Table) và Cung cấp Mock Dataset đa màn hình
- **Bối cảnh**:
  1. Component Bảng dữ liệu (Table) ở Panel Phải chỉ hiển thị 3 cột cố định của batch-run ("Tên Template", "Trạng thái", "Chi tiết"), không hiển thị được các trường dữ liệu của trang Người dùng (`/users`) hay các bảng khác.
  2. Khi kéo Table vào mẫu Tạo mới user, Canvas hiển thị trống: *"Không có mục cần kiểm tra trong dữ liệu hiện tại"* và bị mờ cảnh báo *"Ẩn trong dữ liệu thử nghiệm hiện tại theo điều kiện hiển thị"* do `condition` mặc định là `errors` và mock payload chưa có mảng `items`.
- **Quyết định**:
  1. **Dynamic Cột hiển thị (Columns)**: Viết hàm `get_table_columns_options_for_page(page_code)`. Callback `sync_properties_panel` sinh động các Checkbox cột ở Panel Phải theo đúng Page đang chọn (ví dụ `/users` có `username`, `full_name`, `email`, `roles`, `is_active`, `created_at`...).
  2. **Mock Dataset đa màn hình**: `get_mock_payload_for_page` tự động nạp mảng `items` gồm 3-5 bản ghi mẫu phong phú cho từng màn hình (`user`, `template`, `batch_run`...) giúp Canvas hiển thị bảng dữ liệu sống động ngay tức thì.
  3. **Mặc định điều kiện hiển thị**: Khối Table mới tạo mặc định mang `condition="always"` (Luôn hiển thị) thay vì `errors` để bảng không bị ẩn ngoài ý muốn.

## D-09: Phạm vi dữ liệu Bảng (Table Scope) và Điều kiện hiển thị Đích danh / Toàn bộ
- **Bối cảnh**: Người dùng muốn cấu hình cho component Bảng dữ liệu (Table) có thể lựa chọn linh hoạt giữa việc: chỉ gửi thông tin bảng cho **đích danh người dùng đó** (1 dòng duy nhất của tài khoản được tạo/nhận thư) hoặc gửi **toàn bộ danh sách người dùng** (nhiều dòng).
- **Quyết định**:
  1. **Thuộc tính `table_scope` của Table**: Bổ sung điều khiển `dmc.SegmentedControl` trong thuộc tính Bảng dữ liệu:
     - `all`: "Tất cả danh sách user" -> Hiển thị toàn bộ các bản ghi trong danh sách (tối đa theo `limit`).
     - `target_only`: "Chỉ đích danh user đó" -> Bảng tự động lọc hoặc tổng hợp đúng 1 dòng thông tin của người dùng đích (`user.username` / `username`).
  2. **Live Preview & Email Compiler**:
     - Khi chọn `target_only`: Canvas và Email Renderer chỉ kết xuất 1 dòng duy nhất của đối tượng đích danh (trực quan trên màn hình preview).
     - Khi chạy gửi email thực tế (`USER_CREATED`), nếu không có danh sách `items`, compiler tự động dựng 1 dòng chuẩn từ các biến `user.*` của tài khoản mới tạo.
  3. **Mở rộng `condition`**: Bổ sung `target_only` ("Chỉ khi gửi đích danh user đó") và `all_users` ("Chỉ khi gửi danh sách tất cả user") vào danh mục whitelist `VALID_CONDITIONS` và hàm `evaluate_condition`.

## D-10: Tách luồng gửi email chào mừng người dùng mới (Asynchronous Background Thread)
- **Bối cảnh**: Tại màn hình Quản lý người dùng (`/users`), khi Admin bấm "Lưu" để tạo người dùng mới, hệ thống trước đây gọi `_send_welcome_user_email` đồng bộ. Việc kết nối máy chủ SMTP và gửi thư qua mạng mất từ 2–5 giây (hoặc lâu hơn nếu mạng chậm) khiến modal tạo người dùng bị đơ và không đóng lại ngay cho tới khi gửi xong email.
- **Quyết định**:
  1. Trong `app/services/user.py`: Thêm tham số `async_email: bool = True` vào hàm `create_user`.
  2. Khi `async_email=True` (mặc định cho UI): Sau khi giao dịch cơ sở dữ liệu đã commit thành công và tạo xong tài khoản, hệ thống gọi `_send_welcome_user_email_background` để khởi chạy việc gửi thư trong một luồng daemon (`threading.Thread(daemon=True)`).
  3. Callback Dash `handle_save_user` hoàn thành chỉ trong vài mili-giây, modal tạo người dùng đóng ngay lập tức (`opened=False`) và bảng danh sách người dùng được làm mới tức thì.
  4. Quá trình gửi email chạy ngầm dưới nền hoàn toàn độc lập, tự động bắt lỗi và ghi nhật ký kiểm toán `RECON_AUDIT_LOG` đầy đủ với kết quả thành công hoặc mã lỗi chi tiết mà không làm gián đoạn trải nghiệm người dùng.




