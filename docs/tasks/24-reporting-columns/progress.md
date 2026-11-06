# Tiến độ – 24-reporting-columns

Trạng thái: ✅

## Hồi quy cuối (06/11/2026)
- Test đầy đủ: **850 pass, 5 skip, 0 fail** (814 cuối task 23 + 36 test task 24 mới).
- E2E: **12 pass**.
- Typecheck: **21 lỗi = baseline, 0 mới**. Lint: sạch (ruff auto-fix 4 lỗi import thừa/sắp xếp trong code + test task 24).
- `tasks-dashboard`: 29 task, 22 xong.
- T24-01..T24-10 đều ☑. Không thêm migration, không thêm package.

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Auto-discover column metadata | ✅ | 342ad7b |
| 2 | Editable mapping grid và row drag | ✅ | 51152ec |
| 3 | Format/alignment/width/visibility/total | ✅ | 704ae29 |
| 4 | Preview và schema diff | ✅ | 92361a1 |

## Bước 4 — Preview và schema diff (06/11/2026)
- `get_result_layout(ctx, version_id, target)` (`@requires_menu("report_center")`, T24-10): MỘT metadata cho Viewer (web) và Export (excel) — cùng hàm `_result_layout`, chỉ khác lọc visibility (web → WEB_VISIBLE, excel → EXCEL_VISIBLE); trả {target, columns[{field_name, label, data_type, format_mask, alignment, width, is_total, display_order}], total_row}.
- `preview_result_layout` (T24-08): preview web đọc trực tiếp từ DB, đổi ngay sau mỗi lần lưu mapping.
- `restore_column_order` (report_admin, DRAFT-only, T24-09): đặt lại DISPLAY_ORDER = 10, 20, 30... theo ID (thứ tự discover từ nguồn); audit UPDATE_COLUMN_LAYOUT.
- Schema diff: tái dùng `analyze_version_source` (task 22, T22-08) qua `refresh_columns` (bước 1); không viết thêm hàm diff mới.
- Test: `tests/unit/test_report_column_preview.py` (7 test, T24-05/08/09/10). 36 test pass (discover 7 + grid 13 + rules 9 + preview 7).

## Bước 3 — Format/alignment/width/visibility/total (06/11/2026)
- `_validate_column_rules` (Q2/Q3/Q4/Q5): FORMAT_MASK theo DATA_TYPE (NUMBER {#,##0, #,##0.00, #,##0%, 0, 0.00}, DATE {DD/MM/YYYY, YYYY-MM-DD, MM/YYYY}, DATETIME + mask giờ, STRING/BINARY phải trống); IS_TOTAL chỉ NUMBER; WIDTH NULL = tự động, nếu có thì 40..400; LABEL duy nhất trong version (không phân biệt hoa/thường) — kiểm tra trên trạng thái cuối sau khi áp toàn bộ ở bulk save.
- Test: `tests/unit/test_report_column_rules.py` (9 test, T24-03/04/06/07). T24-05 (web false/excel true) kiểm tra ở bước 4 qua get_result_layout. 29 test pass (rules 9 + grid 13 + discover 7).

## Bước 2 — Editable mapping grid và row drag (06/11/2026)
- `update_column` (report_admin, DRAFT-only): sửa LABEL/FORMAT_MASK/ALIGNMENT/WIDTH/WEB_VISIBLE/EXCEL_VISIBLE/IS_TOTAL; FIELD_NAME/DATA_TYPE/DISPLAY_ORDER readonly (có trong payload → VALIDATION_ERROR); LABEL rỗng → VALIDATION_ERROR; explicit None cho format_mask/width = xóa (NULL), cho bool = lỗi; một transaction + audit UPDATE_COLUMN.
- `update_columns`: lưu cả grid một lần — validate toàn bộ rồi mới ghi (all-or-nothing), audit UPDATE_COLUMN_LAYOUT trên RECON_RPT_TPL_VER.
- `move_column`/`reorder_columns` (T24-02): mẫu move/reorder task 23 (to_index 0-based, đánh lại order bước 10).
- Test: `tests/unit/test_report_column_grid.py` (13 test). 20 test pass (grid 13 + discover 7).

## Bước 1 — Auto-discover column metadata (06/11/2026)
- `app/services/report_column.py` mới: `list_columns` (`@requires_menu("report_center")`, T24-01 — đủ 11 trường, theo DISPLAY_ORDER) và `refresh_columns` (`@requires_menu("report_admin")`, DRAFT-only — chạy lại analyze + apply diff task 22, trả {diff, applied, columns}).
- `column_display_defaults` (report_source.py, Q6): cột mới khi apply diff đặt ALIGNMENT/WIDTH theo type — NUMBER→RIGHT/120, DATE→CENTER/110, DATETIME→CENTER/160, STRING/BINARY→LEFT/180 (trước đây cứng LEFT/NULL).
- Test: `tests/unit/test_report_column_discover.py` (7 test). Test task 22 (diff) vẫn xanh.
