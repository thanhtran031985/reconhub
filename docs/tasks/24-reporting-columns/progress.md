# Tiến độ – 24-reporting-columns

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Auto-discover column metadata | ✅ | 342ad7b |
| 2 | Editable mapping grid và row drag | ✅ | |
| 3 | Format/alignment/width/visibility/total | ⬜ | |
| 4 | Preview và schema diff | ⬜ | |

## Bước 2 — Editable mapping grid và row drag (06/11/2026)
- `update_column` (report_admin, DRAFT-only): sửa LABEL/FORMAT_MASK/ALIGNMENT/WIDTH/WEB_VISIBLE/EXCEL_VISIBLE/IS_TOTAL; FIELD_NAME/DATA_TYPE/DISPLAY_ORDER readonly (có trong payload → VALIDATION_ERROR); LABEL rỗng → VALIDATION_ERROR; explicit None cho format_mask/width = xóa (NULL), cho bool = lỗi; một transaction + audit UPDATE_COLUMN.
- `update_columns`: lưu cả grid một lần — validate toàn bộ rồi mới ghi (all-or-nothing), audit UPDATE_COLUMN_LAYOUT trên RECON_RPT_TPL_VER.
- `move_column`/`reorder_columns` (T24-02): mẫu move/reorder task 23 (to_index 0-based, đánh lại order bước 10).
- Test: `tests/unit/test_report_column_grid.py` (13 test). 20 test pass (grid 13 + discover 7).

## Bước 1 — Auto-discover column metadata (06/11/2026)
- `app/services/report_column.py` mới: `list_columns` (`@requires_menu("report_center")`, T24-01 — đủ 11 trường, theo DISPLAY_ORDER) và `refresh_columns` (`@requires_menu("report_admin")`, DRAFT-only — chạy lại analyze + apply diff task 22, trả {diff, applied, columns}).
- `column_display_defaults` (report_source.py, Q6): cột mới khi apply diff đặt ALIGNMENT/WIDTH theo type — NUMBER→RIGHT/120, DATE→CENTER/110, DATETIME→CENTER/160, STRING/BINARY→LEFT/180 (trước đây cứng LEFT/NULL).
- Test: `tests/unit/test_report_column_discover.py` (7 test). Test task 22 (diff) vẫn xanh.
