# Tiến độ — 08-app-shell-ui

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Component + gallery | ✅ | 2026-11-01 |  |
| 2 | AppShell + banner | 🔄 | 2026-11-01 |  |
| 3 | Màn Templates | ⬜ |  |  |
| 4 | Màn Data Sources | ⬜ |  |  |
| 5 | Màn Người dùng | ⬜ |  |  |

## Nhật ký
### Bước 1 — 2026-11-01 01:51
- Đã làm: Cài đặt trọn vẹn bộ component Dash Mantine tại `app/ui/components/`: `status_chip` (đủ 7 trạng thái kết quả, trạng thái run, trạng thái người dùng, trạng thái template, dữ liệu tạm, môi trường, vai trò — luôn đảm bảo icon lucide và nhãn chữ); `form_field` (hỗ trợ label, description/hint, required asterisk, tự động gán `aria-describedby` trỏ tới thông báo lỗi khi có lỗi); `kpi_card` (thẻ chỉ số chuẩn hoá màu sắc tone ok/crit/warn); `alert_box` (thông báo theo tone kèm icon và nút action); `empty_state` (trạng thái trống với icon, mô tả và nút hành động); `button_primary`, `button_danger`, `button_subtle`; `modal_confirm` (hộp thoại xác nhận thao tác nhạy cảm, hỗ trợ ô gõ từ khóa xác nhận ví dụ XOA); `drawer_right` (ngăn kéo 540px chuẩn); `file_drop` (vùng kéo thả 50MB); `code_block` (hiển thị mã SQL có nút sao chép). Cài đặt các hàm định dạng `app/ui/formatters.py` (`format_currency`, `format_number`, `format_datetime`, `format_bytes`). Tạo trang thư viện `app/ui/pages/dev_gallery.py` tại đường dẫn `/dev/ui`. Viết bộ test `tests/unit/test_ui_components.py`.
- Kiểm tra: `uv run pytest tests/unit/test_ui_components.py` (3 passed); `uv run poe test` (228 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Toàn bộ component UI tuân thủ triệt để design token từ theme DMC và không hardcode mã màu hex trong các trang.
- Việc cần người làm thủ công: Không có.
