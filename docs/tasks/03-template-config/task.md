# 03-template-config — TemplateConfig, version và service template

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ1
- Phụ thuộc: 02
- Nhánh git: feat/03-template-config

## Mục tiêu
Template lưu và validate chặt theo spec 03 (nguồn Bảng/View + cột lọc), có version, export/import JSON; template DTP mẫu hợp lệ.

## Phạm vi
- app/schemas/template_config.py (Pydantic v2) đủ spec 03 + validator chéo
- Validator có kết nối (bảng/cột tồn tại, cột p_from/p_to kiểu ngày); không kết nối được → cảnh báo
- Repo + service template/version: save_draft, clone, archive, export/import, STALE_DATA
- Lỗi validate theo path, vd `db_source.filters[0].column`
- services/diagram.py: 5 sơ đồ Mermaid từ config
- Seed template DTP (DRAFT) gắn ORACLE_TEST nếu có

## Ngoài phạm vi
- describe_source, preview_sql, grain, dry_run (task 05–07)
- Wizard (task 09)

## Thiết kế
- designs/components/Screen02-Templates, Screen03 (bước 3), Screen04-TemplateDiagram

## Spec liên quan
- docs/specs/03_template_config.md
- docs/specs/05 mục 2

## Quyết định kiến trúc
- CONFIG_JSON là nguồn sự thật
- kind=table mặc định

## Các bước
### Bước 1 — Pydantic model
- Làm: model + validator tĩnh
- Test viết trước: sample DTP hợp lệ; ≥18 case lỗi đúng path
- Kiểm tra: `uv run poe test-engine`

### Bước 2 — Validator có kết nối
- Làm: catalog
- Test viết trước: cột sai → COLUMN_NOT_FOUND đúng path (catalog giả); oracle với bảng thật
- Kiểm tra: `uv run poe test`; `uv run poe test-oracle` (VPN; người dùng chạy và dán kết quả)

### Bước 3 — Repo/service version
- Làm: save_draft/activate rule, clone, archive, audit, STALE_DATA
- Test viết trước: integration SQLite
- Kiểm tra: `uv run poe test`

### Bước 4 — Export/import + diagram + seed
- Làm: Export/import + diagram + seed
- Test viết trước: snapshot Mermaid cho DTP; import vào DB trống
- Kiểm tra: `uv run poe test`

## Chấp nhận khi
- [ ] Template DTP lưu/đọc/clone/export/import qua service
- [ ] Lỗi cấu hình chỉ đúng vị trí
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- —
