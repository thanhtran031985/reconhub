# Tiến độ – 23-reporting-parameters

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Parameter CRUD/validation/default resolution | ✅ | |
| 2 | LOV NONE/STATIC/SQL/LOOKUP + cache | ⬜ | |
| 3 | DISPLAY_ROW/ORDER/GRID_SPAN và tổng row <=12 | ⬜ | |
| 4 | Auto-layout, drag/drop, preview | ⬜ | |

## Bước 1 — Parameter CRUD/validation/default resolution (06/11/2026)
- `app/services/report_param.py` mới: `create_param`/`update_param`/`delete_param` (`@requires_menu("report_admin")`, chỉ version DRAFT, một transaction + audit CREATE/UPDATE/DELETE_PARAM); CODE `^[a-zA-Z][a-zA-Z0-9_]{0,59}$` (bind lowercase), trùng CODE → CONFLICT; DATA_TYPE {STRING, NUMBER, DATE, DATETIME, BOOLEAN}, CONTROL_TYPE {TEXT, NUMBER, DATE, SELECT, MULTI_SELECT, DATE_RANGE}; SELECT/MULTI_SELECT bắt buộc LOV ≠ NONE, DATE_RANGE bắt buộc kiểu ngày; DEFAULT_TYPE {NONE, STATIC, TODAY, FIRST_LOV} (TODAY chỉ ngày, FIRST_LOV chỉ khi có LOV, STATIC default kiểm tra theo kiểu); LOV validate cấu trúc (STATIC unique + không rỗng, SQL SELECT-only + Data Source tồn tại, LOOKUP type tồn tại và active, CACHE_SECONDS 0..3600, MAX_ROWS 1..5000); update không đổi CODE; delete chặn khi CODE còn là bind trong SQL version hoặc SQL LOV khác; tạo mới không chỉ row/order thì auto-place (hàng cuối còn chỗ, không thì hàng mới).
- `resolve_param_values` (`@requires_menu("report_center")`): điền default STATIC/TODAY/FIRST_LOV (qua lov_resolver truyền vào — bước 2 nối resolver thật), kiểm tra required/type/range (BETWEEN 2 giá trị từ ≤ đến, IN list không rỗng, DATE_RANGE chuẩn hóa về [from, to]); param không bắt buộc và không có giá trị thì vắng mặt trong kết quả.
- `get_version` (report_template.py): serialization param thêm `default_type`/`default_value` (trước đây thiếu).
- Test: `tests/unit/test_report_param_crud.py` (T23-01/T23-05/T23-06). 22 test pass; test task 21 (reporting services/audit) vẫn xanh.
