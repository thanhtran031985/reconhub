# Quyết định — 104-layout-cache-perf

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-25 | Tách callback `update_app_shell_container` khỏi hàm thuần `render_app_shell` | Giữ tương thích 100% với các unit/E2E tests gọi trực tiếp `render_app_shell(route, False)` nhận về 1 cây component đơn thay vì tuple | Không |
| 2026-11-25 | Dùng `WeakKeyDictionary[Engine, ...]` cho cache metadata/sidebar và clear trong `clear_perm_cache()` | Tránh tái sử dụng `id(engine)` giữa các test fixture SQLite tạm thời và đảm bảo test độc lập hoàn toàn | Không |
| 2026-11-26 | Cập nhật 2 assertion trong `tests/unit/test_page_report_runs.py` sang kiểm tra `handle_runs_refresh` | Bước 2 chuyển `report_runs.layout()` sang Skeleton-first (`rowData=None`), dữ liệu run theo phân quyền được nạp qua `handle_runs_refresh` | Không |
| 2026-11-26 | Gom thanh công cụ Saved Views (`/templates`, `/report-runs`, `/batches`) vào component dùng chung `app/ui/components/saved_view_toolbar.py` | Tránh trùng lặp giao diện/style giữa từng page riêng lẻ để dễ bảo trì, đồng bộ border mờ cho 3 nút phụ (`Đặt mặc định`, `Khôi phục gốc`, `Xóa View`) mà vẫn giữ nguyên ID cũ của từng trang | Không |

## Câu hỏi còn mở
- Không có.
