# Tiến độ – 24-reporting-columns

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Auto-discover column metadata | ✅ | |
| 2 | Editable mapping grid và row drag | ⬜ | |
| 3 | Format/alignment/width/visibility/total | ⬜ | |
| 4 | Preview và schema diff | ⬜ | |

## Bước 1 — Auto-discover column metadata (06/11/2026)
- `app/services/report_column.py` mới: `list_columns` (`@requires_menu("report_center")`, T24-01 — đủ 11 trường, theo DISPLAY_ORDER) và `refresh_columns` (`@requires_menu("report_admin")`, DRAFT-only — chạy lại analyze + apply diff task 22, trả {diff, applied, columns}).
- `column_display_defaults` (report_source.py, Q6): cột mới khi apply diff đặt ALIGNMENT/WIDTH theo type — NUMBER→RIGHT/120, DATE→CENTER/110, DATETIME→CENTER/160, STRING/BINARY→LEFT/180 (trước đây cứng LEFT/NULL).
- Test: `tests/unit/test_report_column_discover.py` (7 test). Test task 22 (diff) vẫn xanh.
