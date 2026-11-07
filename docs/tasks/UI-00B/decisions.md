# Quyết định kỹ thuật — TASK UI-00B: Fluent Foundation

| Ngày | Quyết định | Lý do | Ảnh hưởng spec |
|---|---|---|---|
| 2026-11-07 | Áp dụng Quartz Fluent theme cho AgGrid thông qua class `ag-theme-quartz-auto-dark` và CSS biến token | Đảm bảo bảng dữ liệu tự động chuyển dark/light mode theo Mantine mà không cần reload page | Phù hợp `designs/tokens.json` |
| 2026-11-07 | Vùng nội dung `AppShellMain` dùng `overflowY: "auto"` cho `page_container` | Đảm bảo các trang cũ chưa migrate không bị cắt nội dung, trong khi các trang mới sử dụng `height: 100%` sẽ triệt tiêu scrollbar ngoài | Không ảnh hưởng chức năng cũ |
| 2026-11-07 | Giữ nguyên 100% component hiện có trong `app/ui/components/` | Đảm bảo backward compatibility cho 26 pages hiện tại trong suốt quá trình migration từng bước | Không ảnh hưởng ngược |

