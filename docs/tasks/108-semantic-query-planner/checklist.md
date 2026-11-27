# Checklist kiểm thử — 108-semantic-query-planner

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task `108-semantic-query-planner` (Semantic Query Planner, Dialect & RLS Metadata Enforcement).

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Query 1 Fact + 1 Dimension / nhiều Dimensions trên SQLite Star Schema | Sinh đúng `LEFT OUTER JOIN` / `INNER JOIN`, `GROUP BY`, số liệu tổng hợp khớp chính xác | ✅ |
| **TC-FN-02** | Đầy đủ phép tổng hợp & Calculated AST Measure | `SUM`, `COUNT`, `COUNT_DISTINCT`, `AVG`, `MIN`, `MAX` và `DIVIDE` (chia 0 trả NULL nhờ `NULLIF`) cho kết quả đúng trên cả dialect Oracle & SQLite | ✅ |
| **TC-FN-03** | `Virtual Date Hierarchy` (`DAY`, `MONTH`, `QUARTER`, `YEAR`) | Tự nhóm đúng theo ngày/tháng/quý/năm trên cột `DATE`/`DATETIME` không cần bảng `DIM_DATE` riêng | ✅ |
| **TC-FN-04** | Chặn **One Primary Fact Rule** (Multi-fact grain conflict) | Chọn 2 measure thuộc 2 Fact khác grain → chặn trước khi chạy DB, trả lỗi rõ tên measure & grain | ✅ |
| **TC-FN-05** | Chặn **Ambiguous Path** & **Relationship Loop** | Mô hình có 2 đường active tới cùng Dim hoặc có vòng lặp → chặn và nêu rõ đường đi gây nhập nhằng | ✅ |
| **TC-FN-06** | Pin exact `MODEL_VERSION_ID` | Chỉ query version `ACTIVE`; từ chối `DRAFT` hoặc `ARCHIVED` nếu không hợp lệ; thay đổi ở bản Draft mới không ảnh hưởng bản đang chạy | ✅ |
| **TC-FN-07** | Bộ lọc (`=`, `>=`, `<=`, `BETWEEN`, `IN`, `LIKE_PREFIX`, `IS_NULL`, `RELATIVE_DATE`) | Sinh bind param chuẩn xác, escape `%`/`_` ở `LIKE_PREFIX`, ngày giờ theo múi giờ Việt Nam | ✅ |
| **TC-FN-08** | Phân trang, Preview Limit (`500–1000`) & Cardinality Top-N | Trả đúng trang, giới hạn preview từ config trung tâm; chart quá ngưỡng cardinality tự cắt Top-N kèm cờ cảnh báo | ✅ |
| **TC-FN-09** | `request_seq` & Preview Timeout | Trả về `request_seq` khớp request để UI loại bỏ stale response; Oracle `call_timeout` ngắn áp dụng đúng cho preview | ✅ |
| **TC-FN-10** | Admin SQL Debug (`get_semantic_sql_debug`) | Chỉ `ADMIN` xem được SQL read-only đã sinh (đã che/chuẩn hóa bind values); user thường bị `FORBIDDEN` | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Thông báo lỗi ngữ nghĩa thân thiện tiếng Việt | Lỗi Grain conflict, Ambiguous path, Missing field trả `ServiceResult` với thông báo rõ ràng, không lộ stacktrace | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy strict | ✅ |
| **TC-REG-03** | `uv run poe test-engine` | Toàn bộ unit + integration test SQLite xanh không cần VPN Oracle (đã chạy xanh 311/311 ca liên quan; full 2410 ca chưa chạy hết) | ⬜ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ kiểm tra bảo mật tự động đạt | ✅ |
| **TC-SEC-02** | Chống SQL Injection qua Intent/Filter/Sort | Field/alias/operator lạ không nằm trong metadata whitelist bị chặn ngay với `SQL_NOT_ALLOWED`; mọi giá trị đi qua bind param | ✅ |
| **TC-SEC-03** | Read-only SQL Guard (`check_report_sql`) | Mọi SQL sinh bởi Planner đều pass `check_report_sql`, không chứa `;`, `UNION`, `FOR UPDATE`, `DBMS_`, `UTL_` | ✅ |
| **TC-SEC-04** | RLS Server-Side không thể bypass | Dù payload giả mạo tham số tổ chức/user, Planner vẫn ép predicate từ `ctx` phía server; `ORG_SCOPE_HOOK` chưa gán scope tự fail-closed | ✅ |
| **TC-SEC-05** | Bảo vệ nguồn `PROD` (`_check_prod_admin`) | User không phải `ADMIN` không thể chạy preview trực tiếp trên Data Source `ENV='PROD'` | ✅ |
