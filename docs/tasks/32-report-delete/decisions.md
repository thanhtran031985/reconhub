# Quyết định — 32-report-delete

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-10 | Xóa hẳn khỏi DB, không lưu trữ/ẩn | Người dùng chọn qua options widget ("Xóa hẳn khỏi DB") | Thêm service `delete_report` mới thay vì chỉ nối `archive_report` có sẵn |
| 2026-11-10 | Chặn xóa khi báo cáo đã có lần chạy (`CONFLICT`) | ~~Kết quả run DONE là lịch sử đối soát, không xóa kèm~~ — **đã bị thay bằng quyết định dưới đây theo ý người dùng** | — |
| 2026-11-10 | Xóa luôn dù báo cáo đã có lần chạy (cascade cả run + export) | Người dùng chốt: "xóa luôn dù có lần chạy nha bạn"; chấp nhận mất lịch sử kết quả của báo cáo đó | Service xóa thêm `RECON_RPT_EXPORT` → `RECON_REPORT_RUN` trước khi xóa template; audit ghi số run/export đã xóa; test chặn `CONFLICT` đổi thành test xóa kèm run |
| 2026-11-10 | Cascade khi chưa có run: favorite, preset, template → version → param (+LOV), column | FK bắt buộc xóa con trước cha; dữ liệu cấu hình chưa gắn kết quả thì xóa kèm được | Không đổi schema, không migration |
| 2026-11-10 | Nút "Xóa báo cáo" gắn theo `report_id` trên mọi dòng của báo cáo | Dòng chưa có template nhờ đó mới có menu, hết trống cột Thao tác | Menu 3 chấm của dòng có template/version thêm 1 mục cuối (sau Divider) |
| 2026-11-10 | Modal xác nhận bắt buộc, target id giữ trong `dcc.Store` | Tránh xóa nhầm; tránh callback bị kích hoạt lại khi redraw (dash_callback_safety) | Dùng lại `modal_confirm` như `tmpl-delete-modal` |

## Câu hỏi còn mở

- Q0: Báo cáo đã có lần chạy mà vẫn muốn xóa hẳn thì xử lý thế nào?
- Q1: Có cần thêm "Lưu trữ báo cáo" vào menu không?
