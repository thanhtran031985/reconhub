# Decisions — Task 91

## D1 — Guard ở page callback, không sửa service
`handle_ds_active_toggle` đọc `IS_ACTIVE` trong DB và bỏ qua khi trạng
thái đã đúng. Không làm `activate/deactivate_data_source` idempotent
vì: (a) service còn được gọi từ nơi khác với ngữ nghĩa "áp lại trạng
thái + ghi audit" có thể là cố ý; (b) sửa service đổi hành vi toàn cục,
rủi ro hơn; (c) guard ở callback chặn đúng điểm phát sinh (mount firing)
và giữ nguyên hành vi khi user bấm thật.

## D2 — Defer storage load theo tab, không clientside
`load_storage_data` chỉ chạy khi tab `"storage"` đang mở. Đủ để giết
các mount firing trong tab (purge preview, mig modal, purge confirm)
vì nút của chúng không mount cho tới khi tab tải. Không cần chuyển
chúng sang clientside.

## D3 — Guard n_clicks cho purge preview
`handle_purge_preview` thiếu guard click (lỗi theo skill
dash_callback_safety). Thêm `if not n_clicks: raise PreventUpdate`.
Không đổi logic preview khi bấm thật.

## D4 — Drawer trả no_update khi mount, không trả tuple reset
Nhánh mount của `handle_drawer_open` trả `(no_update,) * 12`. An toàn
vì đóng drawer sau Lưu do `handle_save_data_source` đảm nhiệm
(`Output ds-drawer.opened`). Tránh đóng drawer vô tình khi bảng vẽ lại.

## D5 — KHÔNG sửa (đã guard đúng)
- `handle_table_test_connection`: đã có guard `if not trigger_val:
  return no_update` — mount chỉ tốn 1 roundtrip rỗng.
- `toggle_mig_modal`: đã có guard task 65 cho nút mount lại — trả
  `no_update_14`.
- Không chuyển toggle modal sang clientside: D2 đã ngăn chúng mount
  khi mở trang; clientside là việc riêng cho `/templates` (task sau).

## D6 — Không tách task mới cho /templates
User chốt 11:52 14/11/2026: chỉ sửa /data-sources trước. `/templates`
để task sau.
