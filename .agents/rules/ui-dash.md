---
trigger: glob
globs: app/ui/**, tests/e2e/**
description: Quy tắc giao diện Dash Mantine, phong cách Fluent Compact + Master–Detail và chuyển thiết kế từ designs/.
---

## Giao diện Dash Mantine
- designs/ CHỈ ĐỌC. Chỉ đọc designs/components/<Tên>/README.md và preview.html mà task liệt kê. Bảng ánh xạ thành phần → DMC ở designs/README.md mục "Ánh xạ sang Dash Mantine".
- Trước khi dùng component DMC, đọc trang của nó từ https://www.dash-mantine-components.com/llms (DMC 2.x, Mantine v8).
- Theme: app/ui/theme.py sinh bởi uv run poe theme. Không viết hex/px trong page; dùng color="primary", p="md", radius="md" hoặc biến CSS assets/tokens.css. Thiếu token: thêm vào tokens.json, chạy uv run poe design-system và uv run poe theme, báo cáo.
- Page: dash.register_page theo path ở docs/specs/05_services_pages.md mục 3. Mọi page (trừ /login) yêu cầu đăng nhập; page không đủ quyền chuyển tới /forbidden. ID component dạng <page>-<khối>-<tên>.
- Callback chỉ: lấy ctx, validate Pydantic, gọi service, dựng component. Việc > 2 giây giao cho worker.
- Bốn trạng thái: dmc.Skeleton; EmptyState (lý do + một hành động); dmc.Alert lỗi giữ dữ liệu cũ + Thử lại; có dữ liệu.
- Grid kết quả: dag.AgGrid(rowModelType="infinite"), columnDefs dựng từ metadata cột của service; ô lệch class rh-diff.
- Ngày giờ: dmc.DateTimePicker(withSeconds=True, valueFormat="DD/MM/YYYY HH:mm:ss"), giờ Việt Nam. Tiền 24.114.547.250.
- Thao tác xóa (dữ liệu tạm, file SQLite cũ, khóa user): luôn qua dmc.Modal nêu rõ sẽ xóa gì, giữ lại gì; xóa hàng loạt yêu cầu gõ xác nhận.
- Kiểm tra giao diện bằng trình duyệt của Antigravity hoặc Playwright ở 1440×900 và 1366×768, chụp ảnh đính vào báo cáo bước.

## Phong cách: Fluent Compact + Master–Detail
Mẫu đối chiếu: designs/reference/preview-fluent.html (CHỈ ĐỌC). Mọi page dùng một phong cách này; không tự tạo style mới. docs/design/DESIGN_STYLE_PROMPTS.md chỉ để tham khảo, không áp dụng.
Ưu tiên khi mâu thuẫn: tokens.json / rule này > task.md > hướng dẫn trong skill.

### Khung màn hình (không cuộn cả trang)
- Dùng dmc.AppShell trong app/ui/layout/: navbar (thu gọn được về chỉ icon + tooltip), header một dòng (breadcrumb trái; theme, môi trường, user phải). Kích thước navbar/header lấy từ token layout, không đặt trong page.
- Ở 1366×768 trở lên: trang KHÔNG cuộn. Chỉ grid, danh sách, panel cuộn bên trong (dmc.ScrollArea hoặc AgGrid). Vùng chính dùng dmc.Stack có flex 1 và min-height 0 (qua class trong assets/, không style inline).
- Mỗi page gồm 3 vùng theo thứ tự: header trang một dòng (dmc.Title order=4 + dmc.Text c="dimmed" size="sm" cùng hàng, nút chính bên phải) | command bar | vùng chính chiếm phần còn lại. Không dùng khối hero lớn.
- Dưới 900px: cho phép cuộn trang, navbar thành menu trượt (burger), panel chia đôi chuyển thành xếp dọc.

### Mật độ
- Input, Select, Button trong form: size="xs" hoặc "sm" thống nhất theo token; control trong grid/command bar: size="xs". Không dùng size="md" trở lên trong nội dung.
- Khoảng cách: gap="xs", p="sm" cho panel; không dùng p="xl" / gap="xl".
- dmc.Title trong nội dung tối đa order=4; tiêu đề section order=5.
- AgGrid: rowHeight và headerHeight lấy từ hằng số chung trong app/ui/components/ (một nơi), không đặt riêng từng page. Số căn phải, font tabular.
- Danh sách nhiều mục (báo cáo, template, menu, user…): dùng AgGrid hoặc bảng có dòng nhóm, KHÔNG dùng lưới card.

### Mẫu bố cục
- Command bar: dmc.Group gồm ô tìm kiếm, bộ lọc, nút Thêm / Xóa / Xuất; đặt ngay trên grid, trong một dmc.Paper withBorder.
- Màn danh sách: grid chiếm hết chiều cao còn lại.
- Màn cấu hình (tham số & LOV, cột, menu, phân quyền, template, Data Source): MASTER–DETAIL. Trái = grid/danh sách (flex 1); phải = panel thuộc tính độ rộng cố định theo token, nền phụ, viền trái, cuộn độc lập. Chọn dòng → chi tiết hiện ngay bên phải; không mở Modal để sửa.
- Màn xem báo cáo / chạy Run: bộ lọc gọn một hàng (dmc.SimpleGrid tự co cột) + nút chạy; grid kết quả chiếm phần còn lại.
- Wizard: dmc.Stepper size="xs" một hàng ở đầu panel; nút Quay lại / Tiếp theo nằm ở footer cố định của panel, không nổi đè nội dung.
- dmc.Modal chỉ cho xác nhận, thông báo ngắn và thao tác xóa (như mục trên); không dùng Modal làm form dài.

### Hình thức
- dmc.Paper withBorder, radius="sm", shadow="xs" hoặc không bóng. Không gradient, không bo góc lớn, không icon nhiều màu, không hiệu ứng trang trí.
- Mục navbar đang chọn: dmc.NavLink active (nền nhạt màu primary). Icon dash-iconify bộ lucide:, cùng kích thước.
- Màu chỉ dùng cho nút chính, focus, mục đang chọn và trạng thái (luôn kèm icon và chữ).
- Hỗ trợ sáng/tối qua theme; không hardcode màu.

### Tương tác và truy cập
- Mọi control có label hoặc aria-label; focus nhìn thấy rõ.
- Chuyển động chỉ dùng mặc định của Mantine; không thêm animation; tôn trọng prefers-reduced-motion.
- Kết quả/lỗi cập nhật động: đặt trong vùng aria-live="polite".

### Nghiệm thu giao diện (bổ sung cho mục kiểm tra ở trên)
- Playwright e2e ở 1366×768 và 1440×900: document.documentElement.scrollHeight <= innerHeight và không có cuộn ngang, với mọi page trong task.
- Đối chiếu ảnh chụp với designs/reference/preview-fluent.html: mật độ, vị trí command bar, master–detail, footer wizard.
- Báo cáo bước liệt kê ngắn phần giao diện đã đổi; không đổi gì ngoài phạm vi task.
