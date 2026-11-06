# Tiến độ – 23-reporting-parameters

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Parameter CRUD/validation/default resolution | ✅ | 7bd92fa |
| 2 | LOV NONE/STATIC/SQL/LOOKUP + cache | ✅ | d73db3e |
| 3 | DISPLAY_ROW/ORDER/GRID_SPAN và tổng row <=12 | ✅ | c9eee95 |
| 4 | Auto-layout, drag/drop, preview | ✅ | |

## Bước 1 — Parameter CRUD/validation/default resolution (06/11/2026)
- `app/services/report_param.py` mới: `create_param`/`update_param`/`delete_param` (`@requires_menu("report_admin")`, chỉ version DRAFT, một transaction + audit CREATE/UPDATE/DELETE_PARAM); CODE `^[a-zA-Z][a-zA-Z0-9_]{0,59}$` (bind lowercase), trùng CODE → CONFLICT; DATA_TYPE {STRING, NUMBER, DATE, DATETIME, BOOLEAN}, CONTROL_TYPE {TEXT, NUMBER, DATE, SELECT, MULTI_SELECT, DATE_RANGE}; SELECT/MULTI_SELECT bắt buộc LOV ≠ NONE, DATE_RANGE bắt buộc kiểu ngày; DEFAULT_TYPE {NONE, STATIC, TODAY, FIRST_LOV} (TODAY chỉ ngày, FIRST_LOV chỉ khi có LOV, STATIC default kiểm tra theo kiểu); LOV validate cấu trúc (STATIC unique + không rỗng, SQL SELECT-only + Data Source tồn tại, LOOKUP type tồn tại và active, CACHE_SECONDS 0..3600, MAX_ROWS 1..5000); update không đổi CODE; delete chặn khi CODE còn là bind trong SQL version hoặc SQL LOV khác; tạo mới không chỉ row/order thì auto-place (hàng cuối còn chỗ, không thì hàng mới).
- `resolve_param_values` (`@requires_menu("report_center")`): điền default STATIC/TODAY/FIRST_LOV (qua lov_resolver truyền vào — bước 2 nối resolver thật), kiểm tra required/type/range (BETWEEN 2 giá trị từ ≤ đến, IN list không rỗng, DATE_RANGE chuẩn hóa về [from, to]); param không bắt buộc và không có giá trị thì vắng mặt trong kết quả.
- `get_version` (report_template.py): serialization param thêm `default_type`/`default_value` (trước đây thiếu).
- Test: `tests/unit/test_report_param_crud.py` (T23-01/T23-05/T23-06). 22 test pass; test task 21 (reporting services/audit) vẫn xanh.

## Bước 2 — LOV NONE/STATIC/SQL/LOOKUP + cache (06/11/2026)
- `resolve_lov` (`@requires_menu("report_center")`, T23-02/03/04): NONE → []; STATIC → từ STATIC_JSON (kèm entry "Tất cả" value "" theo Q6); SQL → describe kiểm tra alias VALUE/LABEL rồi execute read-only qua `open_checked_connection` (task 22) với binds từ dep_values, `fetchmany(max_rows)` + cắt lại (mặc định 5000); LOOKUP → chỉ mã IS_ACTIVE='Y' (value=LOOKUP_CODE, label=MEANING), sắp xếp DISPLAY_ORDER.
- Cache (dataflow D): key = sha256(Data Source + SQL) : sha256(dep params); đọc RECON_RPT_LOV_CACHE, hit và chưa hết hạn → trả payload; miss → execute rồi ghi cache (EXPIRES_AT = now + CACHE_SECONDS; 0 = không cache); STATIC/LOOKUP không cache DB.
- `invalidate_lov_cache_for_version(conn, version_id)`: xóa cache theo tiền tố base của từng SQL LOV của version; hook vào `activate_version` (report_template.py) cho cả version mới và version cũ bị archive (Q7).
- `resolve_param_values`: mặc định dùng resolver LOV thật cho FIRST_LOV (dep_values = các giá trị đã resolve trước đó); resolver truyền vào vẫn được ưu tiên (test).
- Đổi tên dùng chung trong report_source.py: `_open_checked_connection` → `open_checked_connection`, `_describe_custom_sql` → `describe_report_sql` (task 22 vẫn xanh).
- Test: `tests/unit/test_report_param_lov.py` (16 test). 71 test pass (param 38 + audit + task 22 source).

## Bước 3 — DISPLAY_ROW/ORDER/GRID_SPAN và tổng row ≤12 (06/11/2026)
- `_layout_rows`/`layout_violations` (hàm lõi, lấy conn): gom param IS_VISIBLE='Y' theo DISPLAY_ROW, tổng GRID_SPAN; violation khi > 12. `validate_layout` (`@requires_menu("report_center")`) trả {ok, violations, rows} (T23-07).
- `move_param` (report_admin, DRAFT-only): kéo-thả một param sang hàng/vị trí khác — dùng `to_index` (vị trí 0-based trong hàng đích) thay vì `to_order` như phác thảo ban đầu, vì sau khi đánh lại order theo bước 10 thì giá trị order tuyệt đối không còn ý nghĩa; order các hàng bị ảnh hưởng đánh lại 10/20/30...; audit UPDATE_PARAM.
- `reorder_params` (report_admin, DRAFT-only): xếp lại toàn bộ layout từ `rows=[[id, ...], ...]`; mọi param đang hiển thị phải có mặt đúng một lần (thiếu/thừa/trùng → VALIDATION_ERROR), param ẩn giữ nguyên; audit UPDATE_PARAM_LAYOUT trên RECON_RPT_TPL_VER.
- Q5: create/update cho lưu layout vượt kèm `layout_warnings` trong response (wizard hiện cảnh báo); `activate_version` (report_template.py) chặn khi layout vi phạm (VALIDATION_ERROR); dry-run chặn ở task 25.
- Test: `tests/unit/test_report_param_layout.py` (15 test, T23-06/07/08). 61 test pass (param 53 + audit).

## Bước 4 — Auto-layout, drag/drop, preview (06/11/2026)
- `auto_layout` (report_admin, DRAFT-only, T23-09): xếp lại param hiển thị theo (DISPLAY_ROW, DISPLAY_ORDER) hiện tại vào các hàng ≤ 12 cột, giữ GRID_SPAN; param ẩn giữ nguyên; audit UPDATE_PARAM_LAYOUT.
- `build_param_layout(version_detail, columns=12)` (hàm thuần, không DB): dựng cấu trúc render — rows [{row, total_span, params[{id, code, label, data_type, control_type, required, default_type/value, grid_span, display_order, filter_column/operator, lov, value: None}]}]; columns=1 (mobile) mỗi param một hàng, không đổi dữ liệu đầu vào (T23-11); columns khác 1/12 → VALIDATION_ERROR.
- `preview_layout` (`@requires_menu("report_center")`, T23-10): cùng cấu trúc Viewer dùng (build_param_layout trên dữ liệu version), điền default vào `value` (STATIC/TODAY/FIRST_LOV); param bắt buộc chưa có giá trị thì value None, không lỗi.
- Test: `tests/unit/test_report_param_preview.py` (12 test, T23-09/10/11).
