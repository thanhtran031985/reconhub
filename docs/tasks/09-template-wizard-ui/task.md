# 09-template-wizard-ui — Wizard đăng ký template 5 bước và Sơ đồ diễn giải

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ2
- Phụ thuộc: 07, 08
- Nhánh git: feat/09-template-wizard-ui

## Mục tiêu
Template Owner tự đăng ký template: file mẫu, trường, chọn bảng/view và cột lọc Từ ngày, Đến ngày, Đơn vị (hoặc SQL tự viết), profile, dry-run với khoảng ngày giờ nhập tay, kích hoạt; xem sơ đồ Mermaid.

## Phạm vi
- pages/template_wizard.py: SegmentedControl (Cấu hình | Sơ đồ) + Stepper 5 bước; Store; tự lưu nháp
- Bước 1–2: dcc.Upload + inspect; bảng mapping (pattern-matching ID)
- Bước 3: Data Source; Bảng/View (Select searchable từ list_tables, list_columns); Điều kiện lọc theo tham số; Điều kiện cố định; Câu SELECT sinh ra; SQL tự viết; mapping DB; time_filter
- Bước 4: nút Key/Σ, measures, filters, drilldown, grain, SQL gộp. Bước 5: DateTimePicker có giây, dry-run, kích hoạt
- Tab Sơ đồ: template.diagram, Mermaid qua clientside callback (assets/mermaid.min.js, securityLevel strict), sao chép, fallback

## Ngoài phạm vi
- Kéo thả
- Tô màu cú pháp SQL

## Thiết kế
- designs/components/Screen03-TemplateWizard, Screen04-TemplateDiagram, Stepper, CodeBlock

## Spec liên quan
- docs/PRD.md C3, C4
- docs/specs/03
- docs/specs/05 mục 2–3

## Quyết định kiến trúc
- p_from/p_to luôn source=user, UI khóa

## Các bước
### Bước 1 — Khung + state + autosave
- Làm: Khung + state + autosave
- Test viết trước: hàm config ↔ form; lỗi path map đúng ô
- Kiểm tra: `uv run poe test`

### Bước 2 — Bước 1–2
- Làm: Bước 1–2
- Test viết trước: e2e: upload sample → cảnh báo dòng tổng, 190/200
- Kiểm tra: `uv run poe e2e`

### Bước 3 — Bước 3
- Làm: Bước 3
- Test viết trước: e2e (catalog giả): chọn RECON_SRC.SRC_FACT_INVOICE_DTP, INVOICE_DATE cho p_from/p_to, ORG_CODE cho p_org → SELECT đúng; cột không phải ngày cho p_from → lỗi; SQL có DELETE → lỗi
- Kiểm tra: `uv run poe e2e`

### Bước 4 — Bước 4
- Làm: Bước 4
- Test viết trước: đổi group_by → grain và SQL cập nhật
- Kiểm tra: `uv run poe e2e`

### Bước 5 — Bước 5 + kích hoạt
- Làm: Bước 5 + kích hoạt
- Test viết trước: từ > đến → lỗi; dry-run OK → kích hoạt
- Kiểm tra: `uv run poe e2e`

### Bước 6 — Tab sơ đồ
- Làm: Tab sơ đồ
- Test viết trước: 5 svg hiển thị
- Kiểm tra: `uv run poe e2e`

## Chấp nhận khi
- [ ] Đăng ký template DTP hoàn toàn trên UI
- [ ] Sơ đồ phản ánh đúng cấu hình
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh, e2e xanh

## Câu hỏi mở
- —
