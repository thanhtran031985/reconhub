# Quyết định — 108-semantic-query-planner

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-26 | Tách `app/engine/semantic_planner.py` (graph/rules thuần) khỏi `app/services/semantic_query.py` (DB/ctx/cache) | Đúng nguyên tắc `AGENTS.md` tách hàm thuần ở `app/engine/` để dễ unit test không cần mock phức tạp | Dễ tái sử dụng cho cả Preview ở Task 109 và Export worker |
| 2026-11-26 | Mở rộng `app/engine/sql_dialect.py` hỗ trợ cả `ORACLE` và `SQLITE` | Cho phép chạy toàn bộ integration test Query Planner trong CI không cần VPN Oracle | Bảo đảm mọi hàm cắt ngày/phân trang không phụ thuộc cứng vào hàm riêng của Oracle |
| 2026-11-26 | Chống stale query bằng `request_seq` + `call_timeout` ngắn (20–30s) cho preview | HTTP callback Dash không tự kill cursor đang chạy phía server khi client đổi filter nhanh | An toàn cả phía UI (không ghi đè dữ liệu cũ) và phía DB nguồn |
| 2026-11-27 | Dùng SQL AST compiler thuần Python + `sql_guard.check_report_sql()` thay vì cài `sqlglot` | Nhất quán với `sql_builder.py`/`report_source.py`, không phát sinh thư viện ngoài | Kiểm tra read-only qua `_check_core` cho mọi truy vấn |
| 2026-11-27 | Dùng `@requires_menu("report_center", "report_admin", "report_model", any_of=True)` cho `execute_semantic_preview` | `app/ui/menus.py` chưa có mã `report_studio` (dự kiến ở Task 109) và `test_perm_registry.py` kiểm tra nghiêm ngặt mọi code trong `MENU_BY_CODE` | Task 109 bổ sung menu mới nếu cần |
| 2026-11-27 | Chuẩn hóa output `Virtual Date Hierarchy` về chuỗi ISO (`YYYY-MM-DD`, `YYYY-MM`, `YYYY-QQ`, `YYYY`) trên cả Oracle và SQLite | Đảm bảo biểu đồ/bảng và sắp xếp thời gian giống hệt nhau giữa test SQLite và nguồn Oracle | Bổ sung `date_part_expr` vào `sql_dialect.py` |

## Câu hỏi còn mở
- Không có (đã chốt dùng SQL AST compiler thuần Python kết hợp `sql_guard.py`).
