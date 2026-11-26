# Quyết định — 108-semantic-query-planner

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-26 | Tách `app/engine/semantic_planner.py` (graph/rules thuần) khỏi `app/services/semantic_query.py` (DB/ctx/cache) | Đúng nguyên tắc `AGENTS.md` tách hàm thuần ở `app/engine/` để dễ unit test không cần mock phức tạp | Dễ tái sử dụng cho cả Preview ở Task 109 và Export worker |
| 2026-11-26 | Mở rộng `app/engine/sql_dialect.py` hỗ trợ cả `ORACLE` và `SQLITE` | Cho phép chạy toàn bộ integration test Query Planner trong CI không cần VPN Oracle | Bảo đảm mọi hàm cắt ngày/phân trang không phụ thuộc cứng vào hàm riêng của Oracle |
| 2026-11-26 | Chống stale query bằng `request_seq` + `call_timeout` ngắn (20–30s) cho preview | HTTP callback Dash không tự kill cursor đang chạy phía server khi client đổi filter nhanh | An toàn cả phía UI (không ghi đè dữ liệu cũ) và phía DB nguồn |

## Câu hỏi còn mở
- Bước 3 đánh giá dùng thuần compiler Python + `sql_guard.py` hay thêm `sqlglot` nếu cần parse/verify đa dialect sâu hơn.
