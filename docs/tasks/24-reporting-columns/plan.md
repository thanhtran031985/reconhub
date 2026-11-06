# Implementation Plan — 24-reporting-columns (Column mapping và result layout)

## Bối cảnh
- Phụ thuộc task 23 — đã xong, nhánh `feat/23-reporting-parameters` ở `57b20fb`, đã push lên remote; task 23 không có migration.
- Tài liệu đã có trên nhánh `docs/dynamic-reporting`: spec 12 (§Bước 4 Column mapping, §giới hạn), 12a, 12b.
- Code hiện có tái dùng được:
  - Schema task 21: RECON_RPT_COLUMN (FIELD_NAME, LABEL, DATA_TYPE, DISPLAY_ORDER, WEB_VISIBLE, EXCEL_VISIBLE, FORMAT_MASK nullable, ALIGNMENT check LEFT/CENTER/RIGHT, WIDTH nullable, IS_TOTAL; UQ(VERSION_ID, FIELD_NAME)).
  - `app/services/report_template.py::get_version` đã serialize đủ 11 trường cột.
  - Task 22 `analyze_version_source` + `apply_source_diff`: phát hiện cột mới/mất/đổi type; tạo cột mới với LABEL=FIELD_NAME, WEB/EXCEL_VISIBLE='Y', DISPLAY_ORDER = max+10 (chưa đặt ALIGNMENT/WIDTH theo type — DB default LEFT/NULL).
  - `app/services/report_source.py::map_oracle_type`: kiểu cột là DATE/DATETIME/NUMBER/STRING/BINARY.
  - Task 23: mẫu service `report_param.py` (DRAFT-only, audit cùng transaction, `move_param`/`reorder_params` với to_index, validate rồi mới ghi).
  - Format Excel đã có trong app: `app/engine/export_styles.py` dùng `#,##0` / `#,##0.00`.
- Lưu ý: task này là service + logic layout (test pytest). UI Dash thật (wizard bước 4, Viewer) thuộc task 27; bước 4 ở đây làm hàm layout thuần mà Viewer (task 27) và Export (task 26) dùng chung, không làm page Dash.
- Không thêm migration (schema đủ), không thêm package mới.

## Nhánh và tài liệu
- Nhánh mới `feat/24-reporting-columns` từ `57b20fb` (đầu nhánh task 23 trên remote).
- Chép `docs/tasks/24-reporting-columns/` từ nhánh docs vào nhánh mới (task/progress/decisions/test-checklist; plan.md chép nguyên văn plan này sau khi duyệt).
- Spec 12/12a/12b + Screen16 ở lại nhánh `docs/dynamic-reporting` làm tham chiếu, không đưa vào patch task 24.

## Các bước (theo progress.md)

### Bước 1 — Auto-discover column metadata
- Service mới `app/services/report_column.py` (`@service`, `@requires_menu("report_admin")` cho ghi, `report_center` cho đọc).
- `list_columns(ctx, version_id)` (T24-01): trả toàn bộ cột của version kèm đủ 11 trường (id, field_name readonly, label, data_type, display_order, web_visible, excel_visible, format_mask, alignment, width, is_total), sắp xếp DISPLAY_ORDER.
- `refresh_columns(ctx, version_id)` (DRAFT-only): chạy lại `analyze_version_source` + `apply_source_diff` (task 22) để nhận cột mới/mất/đổi type sau re-analyze, trả diff {added, removed, type_changed} + grid hiện tại. Cột mới được tạo với default theo type (xem Q6).
- Mở rộng `apply_source_diff` (report_source.py): khi tạo cột mới, đặt ALIGNMENT/WIDTH mặc định theo DATA_TYPE (Q6) thay vì để DB default LEFT/NULL.
- Test trước: `tests/unit/test_report_column_discover.py` — T24-01 (grid đủ field), refresh thêm cột mới + ẩn cột mất + đổi type (mock Oracle theo mẫu task 22), default alignment/width theo type.
- Kiểm tra: `uv run poe test` (phạm vi unit), `uv run poe lint`, `uv run poe typecheck`.

### Bước 2 — Editable mapping grid và row drag
- `update_column(ctx, version_id, column_id, payload)` (DRAFT-only): sửa LABEL/FORMAT_MASK/ALIGNMENT/WIDTH/WEB_VISIBLE/EXCEL_VISIBLE/IS_TOTAL; FIELD_NAME và DATA_TYPE là readonly (đổi trong payload → VALIDATION_ERROR); DISPLAY_ORDER không sửa trực tiếp (dùng move/reorder); một transaction + audit UPDATE_COLUMN trên RECON_RPT_COLUMN.
- `update_columns(ctx, version_id, rows)` (DRAFT-only): lưu cả grid một lần — validate toàn bộ trước rồi mới ghi (all-or-nothing), một audit UPDATE_COLUMN_LAYOUT trên RECON_RPT_TPL_VER; lỗi ở bất kỳ dòng nào thì không ghi dòng nào (T24-03 trùng label chỉ bắt được khi kiểm tra cả grid cùng lúc).
- `move_column(ctx, version_id, column_id, to_index)` và `reorder_columns(ctx, version_id, ordered_ids)` (DRAFT-only, T24-02): cùng mẫu `move_param`/`reorder_params` task 23 (to_index 0-based, đánh lại order bước 10); audit UPDATE_COLUMN.
- Test trước: `tests/unit/test_report_column_grid.py` — T24-02 (drag trong grid, drag sang vị trí khác), sửa label/format/visibility, sửa FIELD_NAME/DATA_TYPE bị chặn, bulk save all-or-nothing, DRAFT-only, FORBIDDEN.
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 3 — Format/alignment/width/visibility/total
- Validation trong `update_column`/`update_columns` (T24-03..T24-07):
  - LABEL: bắt buộc không rỗng (sau strip), duy nhất trong version (không phân biệt hoa/thường) — T24-03.
  - FORMAT_MASK: theo DATA_TYPE (Q2) — NUMBER: `#,##0`, `#,##0.00`, `#,##0%`, `0`, `0.00`; DATE: `DD/MM/YYYY`, `YYYY-MM-DD`, `MM/YYYY`; DATETIME: các mask của DATE + `DD/MM/YYYY HH:mm`, `DD/MM/YYYY HH:mm:ss`; STRING/BINARY: phải để trống — T24-04.
  - WEB_VISIBLE/EXCEL_VISIBLE: độc lập; cột WEB='N', EXCEL='Y' vẫn xuất Excel (T24-05); cả hai 'N' thì cột vẫn giữ dòng mapping (không xóa) nhưng không hiện ở đâu.
  - IS_TOTAL: chỉ khi DATA_TYPE='NUMBER' (T24-06).
  - WIDTH: NULL = tự động, nếu có thì 40..400 (Q4) — T24-07.
  - ALIGNMENT: LEFT/CENTER/RIGHT (DB check đã có, service báo lỗi thân thiện).
- Test trước: `tests/unit/test_report_column_rules.py` — T24-03 (label rỗng, label trùng hoa/thường), T24-04 (mask sai type, mask đúng type, STRING có mask), T24-05 (web false/excel true qua get_result_layout), T24-06 (total trên STRING/DATE bị chặn), T24-07 (width 39/401 bị chặn, 40/400/NULl được).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 4 — Preview và schema diff
- `get_result_layout(ctx, version_id, target)` (`@requires_menu("report_center")`, target "web"|"excel", T24-10): MỘT metadata cho cả hai — cùng hàm, chỉ khác lọc visibility (web → WEB_VISIBLE='Y', excel → EXCEL_VISIBLE='Y'); trả {columns: [{field_name, label, data_type, format_mask, alignment, width, is_total, display_order}], total_row: bool (có cột IS_TOTAL nào không)}. Viewer (task 27) và Export (task 26) dùng chung hàm này nên metadata nhất quán.
- `preview_result_layout(ctx, version_id)` (T24-08): preview realtime = `get_result_layout` target web đọc trực tiếp từ DB (không cache) nên sau mỗi lần lưu mapping là preview đổi ngay; test chứng minh: sửa mapping rồi preview lại thấy đổi.
- `restore_column_order(ctx, version_id)` (DRAFT-only, T24-09): đặt lại DISPLAY_ORDER = 10, 20, 30... theo ID (thứ tự discover từ nguồn — cột tạo ra theo thứ tự describe, ID tăng dần giữ đúng thứ tự đó); audit UPDATE_COLUMN_LAYOUT.
- Schema diff: tái dùng `analyze_version_source` (task 22, đã test ở T22-08) — `refresh_columns` (bước 1) đã trả diff; không viết thêm hàm diff mới.
- Test trước: `tests/unit/test_report_column_preview.py` — T24-08 (preview đổi ngay sau save), T24-09 (drag lộn xộn rồi restore về đúng thứ tự discover), T24-10 (web/excel cùng field/label/type/format/order, chỉ khác cột bị lọc bởi visibility).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

## Kiểm tra cuối
- `uv run poe test` đầy đủ, `uv run poe e2e`, `uv run poe typecheck` (21 lỗi baseline, 0 mới), `uv run poe lint`.
- Không phá golden/reconcile/batch/permission hiện có; không dùng dữ liệu giả trong production path.

## Câu hỏi chốt (Q0–Q8)
- Q0: Nhánh `feat/24-reporting-columns` từ `57b20fb` (đầu nhánh task 23 đã push). Đồng ý?
- Q1: Làm xong cả task rồi gửi xem như các task trước, hay dừng sau mỗi bước chờ "continue"?
- Q2: Từ vựng FORMAT_MASK theo type: NUMBER {`#,##0`, `#,##0.00`, `#,##0%`, `0`, `0.00`}; DATE {`DD/MM/YYYY`, `YYYY-MM-DD`, `MM/YYYY`}; DATETIME {các mask DATE + `DD/MM/YYYY HH:mm`, `DD/MM/YYYY HH:mm:ss`}; STRING/BINARY phải để trống. Đồng ý?
- Q3: LABEL duy nhất trong version, không phân biệt hoa/thường (T24-03 "trùng"). Đồng ý?
- Q4: WIDTH NULL = tự động, nếu có thì 40..400. Đồng ý?
- Q5: IS_TOTAL chỉ khi DATA_TYPE='NUMBER'. Đồng ý?
- Q6: Default khi auto-discover: ALIGNMENT NUMBER→RIGHT, DATE/DATETIME→CENTER, STRING/BINARY→LEFT; WIDTH NUMBER→120, DATE→110, DATETIME→160, STRING/BINARY→180. Đồng ý?
- Q7: Restore DB order = đặt lại DISPLAY_ORDER theo ID (thứ tự discover từ nguồn). Đồng ý?
- Q8: `get_result_layout(target web/excel)` là MỘT hàm dùng chung cho Viewer và Export (T24-10). Đồng ý?
