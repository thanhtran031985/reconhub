# Implementation Plan — 23-reporting-parameters (Dynamic Parameter, LOV và layout 12 cột)

## Bối cảnh
- Phụ thuộc task 22 — đã xong, nhánh `feat/22-reporting-source` ở `8fd5fc2`, đã push lên remote; migration 0004 đã chạy (alembic_version = 0004_reporting_core).
- Tài liệu đã có trên nhánh `docs/dynamic-reporting`: spec 12 (§Bước 3, §giới hạn), 12a, 12b (luồng D LOV, luồng runtime, luồng F version update).
- Code hiện có tái dùng được:
  - Schema task 21: RECON_RPT_PARAM (CODE/LABEL/DATA_TYPE/CONTROL_TYPE/REQUIRED/DEFAULT_TYPE/VALUE/DISPLAY_ROW/ORDER/GRID_SPAN check 1..12/FILTER_COLUMN/OPERATOR/IS_VISIBLE), RECON_RPT_PARAM_LOV (LOV_TYPE check NONE/STATIC/SQL/LOOKUP, DATA_SOURCE_ID, SQL_TEXT, LOOKUP_TYPE, STATIC_JSON, CACHE_SECONDS, MAX_ROWS mặc định 5000), RECON_RPT_LOV_CACHE (CACHE_KEY/PAYLOAD_JSON/ROW_COUNT/EXPIRES_AT/CREATED_AT).
  - `app/services/report_template.py::get_version` trả params kèm LOV lồng nhau (nhưng thiếu DEFAULT_TYPE/DEFAULT_VALUE trong serialization).
  - `app/services/report_source.py` (task 22): `check_report_sql` (SELECT-only), `validate_version_sql` (describe), `_open_checked_connection` (read-only + timeout min), `build_report_query` (whitelist + bind).
  - `app/services/lookup.py`: `list_lookup_codes` (trả cả inactive, cache theo type), mã có LOOKUP_CODE + MEANING (label) + IS_ACTIVE.
  - Không thêm migration (schema đủ), không thêm package mới.
- Lưu ý: task này là service + logic layout (test pytest). UI Dash thật (wizard bước 3, Viewer) thuộc task 27; bước 4 ở đây làm hàm layout thuần mà Viewer sẽ dùng chung, không làm page Dash.

## Nhánh và tài liệu
- Nhánh mới `feat/23-reporting-parameters` từ `8fd5fc2` (đầu nhánh task 22 trên remote).
- Chép `docs/tasks/23-reporting-parameters/` từ nhánh docs vào nhánh mới (task/progress/decisions/test-checklist; plan.md chép nguyên văn plan này sau khi duyệt).
- Spec 12/12a/12b + Screen16 ở lại nhánh `docs/dynamic-reporting` làm tham chiếu, không đưa vào patch task 23.

## Các bước (theo progress.md)

### Bước 1 — Parameter CRUD/validation/default resolution
- Service mới `app/services/report_param.py` (`@service`, `@requires_menu("report_admin")`, chỉ version DRAFT — như apply_source_diff task 22): `create_param`, `update_param`, `delete_param` trên RECON_RPT_PARAM + RECON_RPT_PARAM_LOV trong một transaction; audit CREATE_PARAM/UPDATE_PARAM/DELETE_PARAM trên RECON_RPT_PARAM cùng transaction (theo mẫu task 21). Xóa param xóa luôn LOV (FK CASCADE) và không xóa khi param đang là bind bắt buộc của SQL? — SQL CUSTOM_SQL vẫn chạy được nếu thiếu param? Không: bind thiếu thì runtime lỗi; nên delete chặn khi CODE còn xuất hiện trong SQL_TEXT của version (VALIDATION_ERROR) — ghi rõ trong decisions.
- Validation: CODE `^[a-zA-Z][a-zA-Z0-9_]{0,59}$` (bind lowercase như p_org/p_from, khác mã report/template uppercase); trùng CODE trong version → CONFLICT; LABEL bắt buộc; DATA_TYPE ∈ {STRING, NUMBER, DATE, DATETIME, BOOLEAN}; CONTROL_TYPE ∈ {TEXT, NUMBER, DATE, SELECT, MULTI_SELECT, DATE_RANGE} với tương thích: SELECT/MULTI_SELECT bắt buộc LOV ≠ NONE, DATE_RANGE bắt buộc DATA_TYPE DATE/DATETIME (xem Q2).
- DEFAULT_TYPE ∈ {NONE, STATIC, TODAY, FIRST_LOV} (xem Q3); DEFAULT_VALUE kiểm tra theo DATA_TYPE (NUMBER parse được, DATE/DATETIME đúng định dạng); TODAY chỉ cho DATE/DATETIME; FIRST_LOV chỉ khi LOV ≠ NONE.
- `resolve_param_values(ctx, version_id, values)` (hàm dùng cho runtime task 25, làm ở đây): điền default (STATIC → DEFAULT_VALUE, TODAY → ngày hiện tại, FIRST_LOV → giá trị đầu của LOV đã resolve), kiểm tra required (thiếu → VALIDATION_ERROR), kiểm tra type (NUMBER/DATE parse), kiểm tra range: BETWEEN đúng 2 giá trị và from ≤ to, IN là list không rỗng, DATE_RANGE from ≤ to (xem Q4 — schema không có cột MIN/MAX).
- Bổ sung `get_version` (report_template.py): serialization param thêm `default_type`/`default_value` (hiện thiếu).
- Test trước: `tests/unit/test_report_param_crud.py` — T23-01 (NONE control theo type), T23-05 (required/default/type/range), T23-06 (GRID_SPAN 1..12, ngoài khoảng → VALIDATION_ERROR), trùng CODE, delete chặn khi còn bind, DRAFT-only, forbidden operator.
- Kiểm tra: `uv run poe test` (phạm vi unit), `uv run poe lint`, `uv run poe typecheck`.

### Bước 2 — LOV NONE/STATIC/SQL/LOOKUP + cache
- `resolve_lov(ctx, version_id, param_id, dep_values=None)` trong `report_param.py`:
  - NONE → [] (input theo data type).
  - STATIC → parse STATIC_JSON [{value, label}]; Value không trùng (T23-02), entry {"value": "", "label": "Tất cả"} được phép (Q6); lỗi JSON/trùng → VALIDATION_ERROR.
  - SQL → kiểm tra SELECT-only bằng `check_report_sql` (task 22), describe để xác nhận có alias VALUE/LABEL, thực thi read-only qua `_open_checked_connection` (task 22) với binds từ dep_values, giới hạn MAX_ROWS (mặc định 5000, T23-03), kết quả [{value, label}].
  - LOOKUP → đọc RECON_LOOKUP_CODE theo LOOKUP_TYPE, chỉ IS_ACTIVE='Y', sắp xếp DISPLAY_ORDER; value=LOOKUP_CODE, label=MEANING (T23-04). Tái dùng `list_lookup_codes` rồi lọc active (ADMIN có đủ menu lookup + report_admin).
  - Cache (dataflow D): key = sha256(Data Source + SQL hash + dep params) cho SQL LOV; đọc RECON_RPT_LOV_CACHE, hit và chưa hết hạn → trả payload; miss → execute rồi ghi cache với EXPIRES_AT = now + CACHE_SECONDS (0 = không cache). STATIC/LOOKUP không cache DB (đọc trực tiếp, rẻ).
  - Helper `invalidate_lov_cache(version_id)` + hook vào `activate_version` (report_template.py) theo dataflow F (Q7).
- Test trước: `tests/unit/test_report_param_lov.py` với kết nối Oracle giả lập (mẫu task 22) — T23-02, T23-03 (VALUE/LABEL, cache hit/miss/hết hạn, limit 5000), T23-04 (chỉ active), SQL LOV không SELECT-only → SQL_NOT_ALLOWED, thiếu alias VALUE/LABEL → SQL_DESCRIBE_FAILED.
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 3 — DISPLAY_ROW/ORDER/GRID_SPAN và tổng row ≤12
- `validate_layout(version_id)` (đọc DB, trả {ok, violations: [{row, total, params}]}): gom param IS_VISIBLE='Y' theo DISPLAY_ROW, tổng GRID_SPAN mỗi hàng ≤ 12; vượt → violation (T23-07).
- Áp dụng: CRUD param cho phép lưu layout vượt (kèm `layout_warnings` trong response để wizard hiện cảnh báo), nhưng `validate_layout` được chặn ở dry-run (task 25) và activate (task 21 — thêm kiểm tra vào `activate_version`) (xem Q5). GRID_SPAN ngoài 1..12 và DISPLAY_ROW < 1 → VALIDATION_ERROR ngay lúc lưu (DB check đã có, service báo lỗi thân thiện).
- `move_param(ctx, version_id, param_id, to_row, to_order)` (DRAFT-only): kéo-thả đổi vị trí/hàng (T23-08) — đặt DISPLAY_ROW/ORDER mới rồi đánh lại DISPLAY_ORDER trong các hàng bị ảnh hưởng (bước 10, 20, 30...); `reorder_params(ctx, version_id, ordered_ids)` cho kéo-thả nhiều mục một lúc.
- Test trước: `tests/unit/test_report_param_layout.py` — T23-06, T23-07 (đủ/vượt, nhiều hàng), T23-08 (drag trong hàng, drag sang hàng khác, drag lên đầu/cuối).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 4 — Auto-layout, drag/drop, preview
- `auto_layout(ctx, version_id)` (DRAFT-only): xếp param IS_VISIBLE='Y' theo DISPLAY_ORDER vào các hàng, mỗi hàng tổng GRID_SPAN ≤ 12 (giữ GRID_SPAN hiện tại nếu 1..12, span không hợp lệ → 6); param mới tạo không chỉ row/span được xếp cuối (create_param mặc định: hàng cuối còn chỗ hoặc hàng mới, GRID_SPAN=6) (T23-09).
- `build_param_layout(version_detail, columns=12)` (hàm thuần, không DB): từ dữ liệu `get_version` dựng cấu trúc render — danh sách hàng, mỗi hàng là danh sách param {code, label, data_type, control_type, required, grid_span, display_order, lov, default} + tổng span; `columns=1` cho mobile: mỗi param một hàng, không đổi metadata (T23-11).
- `preview_layout(ctx, version_id, columns=12)` (service, report_admin + report_center đều đọc được? — preview dùng trong wizard (admin) và Viewer (user có report_center); hàm service dùng `@requires_menu("report_center")` vì Viewer là user thường, wizard admin cũng có menu này — xem Q8): gọi build_param_layout trên dữ liệu version + resolve default; đây là cùng một cấu trúc Viewer (task 27) sẽ dùng để render nên preview khớp Viewer (T23-10).
- Test trước: `tests/unit/test_report_param_preview.py` — T23-09 (auto-layout đủ/vượt/giữ span), T23-10 (preview = cấu trúc Viewer dùng, gồm default đã resolve), T23-11 (mobile 1 cột, metadata không đổi sau khi gọi).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

## Kiểm tra cuối
- `uv run poe test` đầy đủ, `uv run poe e2e`, `uv run poe typecheck` (21 lỗi baseline, 0 mới), `uv run poe lint`.
- Không phá golden/reconcile/batch/permission hiện có; không dùng dữ liệu giả trong production path; không đổi hành vi `get_version` cũ ngoài việc thêm 2 trường default.

## Câu hỏi chốt (Q0–Q8)
- Q0: Nhánh `feat/23-reporting-parameters` từ `8fd5fc2` (đầu nhánh task 22 đã push). Đồng ý?
- Q1: Làm xong cả task rồi gửi xem như task 19/20/21/22, hay dừng sau mỗi bước chờ "continue"?
- Q2: Từ vựng DATA_TYPE {STRING, NUMBER, DATE, DATETIME, BOOLEAN} và CONTROL_TYPE {TEXT, NUMBER, DATE, SELECT, MULTI_SELECT, DATE_RANGE}; SELECT/MULTI_SELECT bắt buộc LOV ≠ NONE, DATE_RANGE bắt buộc DATA_TYPE DATE/DATETIME. Đồng ý?
- Q3: DEFAULT_TYPE {NONE, STATIC, TODAY, FIRST_LOV}; TODAY chỉ DATE/DATETIME, FIRST_LOV chỉ khi LOV ≠ NONE. Đồng ý?
- Q4: T23-05 "range" hiểu là: BETWEEN đúng 2 giá trị và from ≤ to, IN là list không rỗng, DATE_RANGE from ≤ to (schema không có cột MIN/MAX nên không có min/max số). Đồng ý?
- Q5: Layout vượt 12: cho lưu kèm cảnh báo (wizard hiện warning), chặn ở dry-run và activate — không chặn lúc lưu để còn sửa dần. Đồng ý?
- Q6: STATIC cho phép entry {"value": "", "label": "Tất cả"} (optional ALL theo spec). Đồng ý?
- Q7: Thêm hook xóa LOV cache của version vào `activate_version` (theo dataflow F). Đồng ý?
- Q8: `preview_layout` dùng `@requires_menu("report_center")` để cả wizard (admin) và Viewer (user thường) dùng chung một hàm. Đồng ý?
