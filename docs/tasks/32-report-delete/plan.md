# Kế hoạch — 32-report-delete

_Chưa duyệt. Agent chép nguyên văn Implementation Plan đã duyệt vào đây sau khi người dùng duyệt._

## Bối cảnh

- Nhánh: `feat/32-report-delete`, rẽ từ `adecaa7` (đỉnh `feat/31-data-model-explorer`, đã push).
- Vấn đề 1: dòng Report Master chưa có template nào hiện trạng thái "Hoạt động" nhưng cột Thao tác trống — vì `render_report_list` chỉ thêm nút Sửa khi có `tpl_id` và menu 3 chấm chỉ khi `menu_items` không rỗng, mà cả hai đều `None` với dòng này.
- Vấn đề 2: chưa có action xóa báo cáo nào — không có service `delete_report`; `archive_report` có nhưng chưa nối UI.
- Người dùng đã chốt hướng **xóa hẳn khỏi DB** (10/11/2026, chọn qua options widget).

## Cách làm

### Bước 1 — Service `delete_report` + test viết trước

- File chính: `app/services/report.py` (thêm import `delete` từ SQLAlchemy và các bảng `recon_report_template`, `recon_rpt_tpl_ver`, `recon_rpt_param`, `recon_rpt_param_lov`, `recon_rpt_column`, `recon_rpt_preset`, `recon_report_run`).
- Hàm mới `@service` + `@requires_menu("report_admin")`:
  - Load dòng report với `admin=True` (lạ → `NOT_FOUND`).
  - Xóa luôn dù báo cáo đã có lần chạy (quyết định của người dùng
    10/11/2026, sửa lại ý chặn ban đầu): trong cùng một transaction,
    xóa export của các lần chạy rồi xóa lần chạy; xóa favorite + preset;
    với mỗi template: đặt `ACTIVE_VERSION_ID=None`, rồi với mỗi version:
    xóa LOV của tham số, xóa tham số, xóa cột, xóa version; xóa template;
    cuối cùng xóa báo cáo. Ghi audit `DELETE_REPORT` (`old_data`: code,
    name, số template/version/lần chạy/export đã xóa).
- Thêm `("report", "delete_report"): ["report_admin"]` vào `tests/unit/test_perm_registry.py`.
- Test viết trước (đỏ → xanh): `tests/unit/test_reporting_services.py` (xóa report trống; cascade template/version/param + LOV/column/preset/favorite; xóa report đã có run DONE + export thì run, export và template đều bị xóa hẳn; `FORBIDDEN` với operator; `NOT_FOUND`); `tests/unit/test_reporting_audit.py` (xóa thành công ghi 1 dòng `DELETE_REPORT` kèm số lượng đã xóa).
- Kiểm tra: `uv run poe test -- tests/unit/test_reporting_services.py tests/unit/test_reporting_audit.py tests/unit/test_perm_registry.py -q` xanh.

### Bước 2 — UI: mục "Xóa" + modal xác nhận + callback

- File duy nhất: `app/ui/pages/report_admin.py` (thêm import `delete_report` từ `app.services.report` và `modal_confirm` từ `app.ui.components`).
- `render_report_list`: thêm `dmc.MenuItem("Xóa báo cáo", id={"type": "admin-delete-report", "index": report_id}, color="red", leftSection=DashIconify(icon="lucide:trash-2", width=14))` vào cuối `menu_items` của mọi dòng; thêm `dmc.Divider()` trước nó khi menu đã có item khác. Dòng chưa có template giờ có menu chỉ gồm "Xóa báo cáo" nên cột Thao tác không còn trống.
- `layout`: thêm `modal_confirm(id="admin-delete-modal", title="Xác nhận xóa vĩnh viễn báo cáo", description="...mã + tên báo cáo... không thể khôi phục.", confirm_label="Xóa vĩnh viễn")` + `dcc.Store(id="admin-delete-target-id")`, đặt ngoài container mà callback khác dựng lại.
- 2 callback mới (theo `dash_callback_safety`): mở modal (Input nút Xóa pattern-matching `ALL` + nút Hủy trong modal; guard `not any(n_clicks)` → `PreventUpdate`; chỉ mở khi trigger đúng là nút Xóa, lưu `report_id` vào store) và xác nhận xóa (Input nút xác nhận trong modal; guard target `None` → `PreventUpdate`; gọi `delete_report`, lỗi thì `_err_alert`, thành công thì `notify_success` + tải lại danh sách bằng `_load_reports_with_templates`).
- Test viết trước (đỏ → xanh): `tests/unit/test_page_report_admin.py` — dòng report chưa có template render ra menu chứa "Xóa báo cáo"; gọi trực tiếp 2 callback với `n_clicks=None`/`[0]` thì không xóa/không mở modal, với `[1]` thì mở modal đúng 1 lần và xóa đúng 1 lần.
- Kiểm tra: `uv run poe test -- tests/unit/test_page_report_admin.py -q` xanh.

### Bước 3 — Kiểm chứng cuối + xuất patch

- `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh (full suite).
- Kiểm chứng Playwright trên `/report-admin`: mở menu dòng chưa có template → thấy "Xóa báo cáo"; bấm Xóa → modal hiện mã/tên; xác nhận → dòng biến mất; xóa báo cáo đã có run → run và template đều bị xóa hẳn. Chụp màn hình 1440×900 và 1366×768.
- Xuất patch `adecaa7..HEAD`; không cần db-migrate, chỉ khởi động lại app sau khi áp.

## Thứ tự commit (mỗi bước 1 commit)

1. `32-report-delete: step 1 — delete_report service + tests`
2. `32-report-delete: step 2 — delete menu item + confirm modal + callbacks`
3. `32-report-delete: step 3 — final verification` (chỉ khi có sửa chữa sau kiểm chứng; không thì gộp vào bước 2)

## Rủi ro

- Xóa hẳn là thao tác phá hủy: giảm rủi ro bằng modal xác nhận (bắt buộc bấm mới trong modal, hiện rõ mã + tên báo cáo) và test guard callback theo `dash_callback_safety` để một lần redraw không kích hoạt xóa hai lần. Lưu ý: xóa báo cáo đã có lần chạy sẽ mất luôn lịch sử kết quả của báo cáo đó, không khôi phục được.
- FK trên Oracle: thứ tự xóa con trước cha đã tính sẵn (LOV → param/column → version → template → report); nếu Oracle báo lỗi FK thì dừng và báo, không đổi thứ tự bằng cách sửa tay.
- `render_report_list` dựng lại sau mỗi lần lọc/phân trang: nút Xóa dùng pattern-matching id nên callback mở modal phải giữ guard mạnh, không đọc trạng thái từ nút đã bị dựng lại (target id giữ trong `dcc.Store`).

## Câu hỏi chốt trước khi code (Q0–Q1 trong task.md)

- Q0: Báo cáo đã có lần chạy mà vẫn muốn xóa hẳn thì xử lý thế nào? Plan hiện tại: **xóa luôn kèm run + export** (người dùng chốt 10/11/2026).
- Q1: Có cần thêm "Lưu trữ báo cáo" vào menu không? Plan hiện tại: **không**, task riêng sau.
