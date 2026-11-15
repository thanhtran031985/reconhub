# Tiến độ — 95-db-column-lookup-mapping

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Migration các field của `fact_bill` vào `DB_COLUMN_MAPPING` | ✅ | 2026-11-15 | `95-db-column-lookup-mapping: step 1` |
| 2 | Service tra cứu mapping nhãn cột và khởi tạo nhãn khi tạo template | ✅ | 2026-11-15 | `95-db-column-lookup-mapping: step 2` |
| 3 | Bảo vệ giá trị user đã nhập khi mở lại / edit template | ✅ | 2026-11-15 | `95-db-column-lookup-mapping: step 3` |
| 4 | Kiểm thử hồi quy, tích hợp UI và hoàn tất task | ✅ | 2026-11-15 | `95-db-column-lookup-mapping: step 4` |

## Nhật ký
- 2026-11-15:
  - Tạo task theo yêu cầu người dùng, thiết lập mục tiêu, phạm vi, kế hoạch chi tiết và `checklist.md`.
  - Cập nhật `.agents/skills/tao-task/SKILL.md` và `docs/tasks/_template/checklist.md` để mọi task mới đều tự động có `checklist.md`.
  - Bước 1: Tạo Alembic migration `0013_fact_bill_col_map`, bổ sung `FACT_BILL_COLUMNS` và `migrate_fact_bill_columns` vào `app/services/lookup.py`. Đã migrate đủ 119 cột vào `RECON_LOOKUP_CODE` loại `DB_COLUMN_MAPPING` trên SQLite, bảo toàn 7 mã cũ.
  - Bước 2: Bổ sung `get_db_column_mappings` với in-memory cache. Cập nhật `apply_source_diff` trong `app/services/report_source.py` để gán nhãn khởi tạo theo lookup (so sánh upper case); nếu không có thì fallback về Title Case.
  - Bước 3: Cập nhật `_load_columns`, `_column_dict` trong `app/services/report_column.py`, `report_run.py`, `report_template.py`: khi template đã lưu nhãn, giữ nguyên 100% nhãn user đã lưu, tuyệt đối không tự động đè lại từ lookup khi edit.
  - Bước 4: Viết bộ 6 test cases trong `tests/unit/test_task95_lookup_mapping.py` kiểm thử toàn diện các case trong `checklist.md`. Chạy `uv run poe lint`, `uv run poe typecheck`, `uv run pytest` đều xanh 100%. Hoàn tất task.
  - Sửa lỗi phát sinh trên trang `/lookups`: Chẩn đoán và xử lý triệt để lỗi "Page Unresponsive" khi bấm sửa và lưu mã code. Nguyên nhân do `cb_edit_code_modal`, `cb_delete_code_modal`, `cb_delete_type_modal` trả về `False` khi remount component thay vì `raise PreventUpdate`, tạo vòng lặp vô tận với `cb_trigger_refresh`. Đã chuyển sang `PreventUpdate`. Đồng thời bổ sung phân trang (`dmc.Pagination`, 15 dòng/trang, `lookups-code-page-store`) cho bảng Lookup Code và `trapFocus=False` cho `dmc.Modal`, giảm 90% tải DOM (từ 1.800 node xuống ~150 node), loại bỏ triệt để hiện tượng khóa Main Thread trình duyệt khi đóng mở modal với 119 mã. Toàn bộ 77 unit tests liên quan passed 100%, `poe lint` và `poe typecheck` xanh.
