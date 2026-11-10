# 32-report-delete — Xóa hẳn báo cáo (Report Master) trên /report-admin

- Ngày tạo: 2026-11-10
- Giai đoạn: GĐ3
- Phụ thuộc: 21, 27, 28
- Nhánh git: feat/32-report-delete (rẽ từ `adecaa7`, đỉnh `feat/31-data-model-explorer` đã push)

## Mục tiêu

Bổ sung action xóa hẳn báo cáo trên trang `/report-admin`, đồng thời sửa cột
Thao tác đang trống với các báo cáo chưa có template nào.

## Vấn đề (phát hiện 10/11/2026, đã phân tích, chưa code)

1. Dòng Report Master chưa có template nào hiện trạng thái "Hoạt động" nhưng
   cột Thao tác trống hoàn toàn. Nguyên nhân gốc trong
   `app/ui/pages/report_admin.py`, hàm `render_report_list`:
   - Dòng không có template được dựng với `tpl_id=None, ver_id=None`,
     tên hiện "Chưa có template", trạng thái lấy từ report
     (`ACTIVE` nếu `IS_ACTIVE='Y'` nên chip hiện "Hoạt động").
   - Nút Sửa nhanh chỉ render khi có `tpl_id`; menu 3 chấm chỉ render khi
     `menu_items` không rỗng, mà menu chỉ được thêm khi có `tpl_id` (Sửa)
     hoặc `ver_id` (Clone, Lưu trữ version). Cả hai đều `None` nên cả hai
     chỗ đều rơi về `html.Div()` trống.
   - Dòng nào đã có template/version luôn có ít nhất nút Sửa nên không trống.
2. Chưa có action xóa nào cho báo cáo:
   - Không có service `delete_report` / `delete_template` cho báo cáo động.
   - `archive_report` (`app/services/report.py:234`, đổi `IS_ACTIVE='N'`,
     có ghi audit) đã có nhưng chưa nối vào giao diện; menu danh sách hiện
     chỉ có Sửa, Clone, Lưu trữ version.
   - Xóa hẳn không đơn giản: `RECON_REPORT` bị tham chiếu bởi
     `RECON_REPORT_TEMPLATE`, `RECON_REPORT_RUN`, `RECON_RPT_FAVORITE`,
     `RECON_RPT_PRESET`; template kéo theo version, tham số (+LOV), cột;
     lần chạy kéo theo export.

## Quyết định đã chốt với người dùng (10/11/2026)

- **Xóa hẳn khỏi DB**, không phải lưu trữ/ẩn. Người dùng chọn qua options
  widget sau khi được trình 2 hướng ("Xóa hẳn khỏi DB" / "Chỉ lưu trữ").

## Phạm vi

- Service `delete_report` mới trong `app/services/report.py` (chỉ ADMIN,
  menu `report_admin`, 1 transaction, ghi audit `DELETE_REPORT`).
  Xóa luôn dù báo cáo đã có lần chạy: cascade cả run + export.
- UI `/report-admin`: mục "Xóa" trong menu 3 chấm + modal xác nhận.
- Không đổi schema, không migration.
- Chỉ xóa cấp báo cáo (Report Master). Không thêm xóa riêng cấp
  template/version trong task này.

## Ngoài phạm vi

- Xóa báo cáo đã có lần chạy (bị chặn, xem "Quyết định kiến trúc").
- Lưu trữ báo cáo từ UI (nối `archive_report` vào menu) — nếu người dùng
  muốn thì làm task riêng.
- Xóa template đối soát cũ (`app/services/template.py:delete_template`
  đã có, không đụng).

## Thiết kế

- Tái dùng `modal_confirm` (`app/ui/components/modal_confirm.py`) như
  `tmpl-delete-modal` ở `app/ui/pages/templates.py`.
- Callback tuân thủ `~/workspace/custom-skills/dash_callback_safety/SKILL.md`:
  `prevent_initial_call`, guard `n_clicks` falsy, giữ target id trong
  `dcc.Store`, xác nhận bằng một cú bấm mới trong modal.

## Spec liên quan

- Task 21 (Reporting Core, `RECON_REPORT` + versioning), task 27 (UI
  `/report-admin` + wizard), task 28 (permission/audit).

## Quyết định kiến trúc

- **Xóa luôn dù báo cáo đã có lần chạy** (`RECON_REPORT_RUN` + `RECON_RPT_EXPORT`):
  theo quyết định của người dùng ngày 10/11/2026 (sửa lại quyết định chặn
  ban đầu). Lý do: người dùng muốn xóa hẳn, chấp nhận mất lịch sử kết quả
  của báo cáo đó.
- **Cascade khi xóa** (cùng transaction, thứ tự tránh vi phạm FK): export
  của các lần chạy → lần chạy; favorite + preset của báo cáo; với mỗi
  template: đặt `ACTIVE_VERSION_ID=None`, rồi với mỗi version: xóa LOV
  của tham số, xóa tham số, xóa cột, xóa version; xóa template; cuối
  cùng xóa báo cáo. Audit ghi cả số lần chạy/export đã xóa.
- **Nút "Xóa" gắn theo `report_id` trên mọi dòng** của cùng một báo cáo
  (kể cả dòng đã có template/version), nhãn "Xóa báo cáo", màu đỏ,
  icon `lucide:trash-2`. Với dòng chưa có template, menu giờ chỉ có
  "Xóa" nên cột Thao tác không còn trống.
- Modal xác nhận hiện mã + tên báo cáo và cảnh báo không thể khôi phục;
  chỉ bấm "Xóa vĩnh viễn" trong modal mới gọi service.

## Các bước

### Bước 1 — Service `delete_report` + test viết trước
- Làm: `app/services/report.py` — hàm mới `@service` + `@requires_menu("report_admin")`,
  xóa luôn dù báo cáo đã có lần chạy, cascade như trên, audit `DELETE_REPORT`
  (`old_data`: code, name, số template/version/lần chạy/export đã xóa).
  Thêm `("report", "delete_report"): ["report_admin"]` vào
  `tests/unit/test_perm_registry.py`.
- Test viết trước: `tests/unit/test_reporting_services.py` — xóa report
  trống thành công; cascade template/version/param (+LOV)/column/preset/
  favorite; xóa report đã có run DONE + export thì run, export và template
  đều bị xóa hẳn; `FORBIDDEN` với operator; `NOT_FOUND` với id lạ.
  Audit: `tests/unit/test_reporting_audit.py` — xóa thành công ghi 1 dòng
  `DELETE_REPORT` (kèm số lượng đã xóa).
- Kiểm tra: `uv run poe test -- tests/unit/test_reporting_services.py tests/unit/test_reporting_audit.py tests/unit/test_perm_registry.py -q` xanh.

### Bước 2 — UI: mục "Xóa" + modal xác nhận + callback
- Làm: `app/ui/pages/report_admin.py`
  - `render_report_list`: thêm `dmc.MenuItem("Xóa báo cáo",
    id={"type": "admin-delete-report", "index": report_id}, color="red",
    leftSection=DashIconify(icon="lucide:trash-2", width=14))` vào cuối
    `menu_items` của mọi dòng; thêm `dmc.Divider()` trước nó khi menu
    đã có item khác.
  - `layout`: thêm `modal_confirm(id="admin-delete-modal",
    title="Xác nhận xóa vĩnh viễn báo cáo", ...)` +
    `dcc.Store(id="admin-delete-target-id")` (đặt ngoài container mà
    callback khác dựng lại, tránh bấm xóa bị kích hoạt lại khi redraw).
  - Callback mở modal: Input `{"type": "admin-delete-report", "index": ALL}`
    `n_clicks` + Input `admin-delete-modal-cancel`; guard `not any(n_clicks)`
    → `PreventUpdate`; chỉ mở khi đúng trigger là nút Xóa, lưu `report_id`
    vào store. Callback xác nhận: Input `admin-delete-modal-confirm`,
    State target id; guard target `None` → `PreventUpdate`; gọi
    `delete_report`, lỗi thì `_err_alert`, thành công thì
    `notify_success("Đã xóa báo cáo <CODE>.")` + tải lại danh sách
    (`_load_reports_with_templates`).
- Test viết trước: `tests/unit/test_page_report_admin.py` — dòng report
  chưa có template render ra menu chứa "Xóa báo cáo"; gọi trực tiếp 2
  callback với `n_clicks=None`/`[0]` thì không xóa/không mở modal,
  với `[1]` thì mở modal đúng 1 lần và xóa đúng 1 lần (theo
  `dash_callback_safety`).
- Kiểm tra: `uv run poe test -- tests/unit/test_page_report_admin.py -q` xanh.

### Bước 3 — Kiểm chứng cuối + xuất patch
- Làm: chạy full suite + typecheck + lint; kiểm chứng Playwright trên
  `/report-admin` (mở menu dòng chưa có template → thấy "Xóa báo cáo";
  bấm Xóa → modal hiện mã/tên; xác nhận → dòng biến mất; thử xóa báo cáo
  đã có run → báo chặn, dữ liệu còn nguyên); chụp màn hình.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe test`
  xanh; `uv run poe e2e` cho page report-admin nếu có.
- Xuất patch `adecaa7..HEAD`, không cần db-migrate, chỉ khởi động lại app
  sau khi áp.

## Chấp nhận khi

- [ ] Dòng báo cáo chưa có template có menu 3 chấm với "Xóa báo cáo",
      cột Thao tác không còn trống.
- [ ] Xóa báo cáo trống/có template (kể cả đã có run) xóa hẳn khỏi DB kèm
      favorite/preset/template/version/param/column/run/export, có audit.
- [ ] Chỉ ADMIN thấy/làm được; operator bị `FORBIDDEN`.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh.

### Data Model Impact
- [ ] Task không thay đổi database schema.

## Câu hỏi mở

- Q0: Báo cáo đã có lần chạy mà người dùng vẫn muốn xóa hẳn thì xử lý
  thế nào (xóa kèm run + export, hay giữ nguyên chặn)? Hiện chốt **xóa
  luôn kèm run + export** theo ý người dùng ngày 10/11/2026.
- Q1: Có cần thêm "Lưu trữ báo cáo" vào menu (nối `archive_report` sẵn có)
  cho trường hợp không xóa hẳn được không?
