# TASK UI-05 — Template Wizard

## Status

TODO

## Dependencies

- UI-00B (Fluent Foundation)

## Objective

Chuyển đổi quy trình đăng ký và chỉnh sửa template (`/templates/new` và `/templates/<id>/edit`) sang pattern **WIZARD** chuẩn Fluent Compact: `PageHeader` + `Stepper` 1 hàng compact ở đỉnh + Vùng nội dung bước `flex: 1` (cuộn nội bộ) + Footer thanh điều hướng cố định chân trang (Back / Next / Save Draft).
Triệt tiêu hoàn toàn hiện tượng cuộn trang kéo dài (hiện tại trang Edit cuộn tới 1778px), đồng thời thiết lập bộ regression test toàn diện cho New, Edit, Next, Back, Save Draft, Validation và Reload draft để đảm bảo tính toàn vẹn 100% của quy trình nghiệp vụ cốt lõi.

> [!IMPORTANT]
> **EXECUTION POLICY**:
> AI chỉ được thực hiện task này khi người dùng chỉ định chính xác: `"Làm UI-05"`.
> Sau khi hoàn thành task này: **STOP**. Không tự động bắt đầu task tiếp theo.

## Pages

| Route | Page Module | Task Gốc Sinh Ra | Spec Liên Quan | Màn Thiết Kế Gốc |
|---|---|---|---|---|
| `/templates/new` | `app/ui/pages/template_wizard.py` | [03-template-config](../03-template-config/task.md) & [09-template-wizard-ui](../09-template-wizard-ui/task.md) | [03_template_config.md](../../specs/03_template_config.md), [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen03-TemplateWizard` |
| `/templates/<id>/edit` | `app/ui/pages/template_wizard.py` | [03-template-config](../03-template-config/task.md) & [09-template-wizard-ui](../09-template-wizard-ui/task.md) | [03_template_config.md](../../specs/03_template_config.md), [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen03-TemplateWizard` |

## Target Pattern

**WIZARD**:
- Header: `PageHeader` (Tên template + mã template + trạng thái bản nháp).
- Stepper: `dmc.Stepper(size="xs")` gói gọn trong 1 hàng ngang ở đỉnh khung làm việc.
- Body: Vùng nội dung bước chiếm `flex: 1, minHeight: 0, overflow: auto` (cuộn độc lập).
  - Bước 1: Thông tin chung (Mã, Tên, Đơn vị, File mẫu).
  - Bước 2: Nguồn dữ liệu (Data Source, Bảng/View/SQL, Cột lọc).
  - Bước 3: Ánh xạ cột (Excel ↔ DB ↔ Logic field, Grain keys, Measures, Sai số).
  - Bước 4: Kiểm tra Dry-run & Hoàn tất.
- Footer: Thanh điều hướng cố định chân trang (nền `surface-2`, viền trên `line`), chứa các nút: `Quay lại`, `Lưu nháp`, `Tiếp theo`, `Kích hoạt template`.

## Read First

1. `AGENTS.md`
2. `.agents/rules/ui-dash.md`
3. `docs/specs/03_template_config.md`
4. `docs/ui-migration.md` (mục 3, 4, 10 cho UI-05)
5. Yêu cầu & nghiệp vụ gốc:
   - [03-template-config/task.md](../03-template-config/task.md) (Cấu trúc TemplateConfig, versioning và auto-draft)
   - [09-template-wizard-ui/task.md](../09-template-wizard-ui/task.md) (Wizard đăng ký template 5 bước ban đầu)
6. Baseline screenshots: `artifacts/ui-inventory/template-wizard-new-before-1366x768.png`, `template-wizard-edit-before-1366x768.png`
7. Component `WizardShell` từ UI-00B

## Allowed Scope

- Cập nhật cấu trúc layout trong `app/ui/pages/template_wizard.py`:
  - Tích hợp `PageHeader` và `WizardShell`.
  - Đưa `dmc.Stepper` về `size="xs"` compact.
  - Cố định footer thanh điều hướng ở chân trang không bị trôi theo nội dung.
  - Đảm bảo các khung Mapping cột, Editor SQL, Bảng preview dữ liệu đều có `overflow: auto` bên trong body.
- Viết bộ regression tests toàn diện tại `tests/e2e/test_template_wizard_regression.py`.

## Forbidden Scope

- **TUYỆT ĐỐI KHÔNG SỬA**:
  - `dcc.Store(id="tmpl-wiz-config-store")` và cấu trúc `TemplateConfig` Pydantic model.
  - Cơ chế tự động lưu nháp qua `dcc.Interval` và kiểm tra hash thay đổi.
  - Bộ kiểm tra an toàn SQL Guard (`app/engine/sql_builder.py` và describe source).
  - Logic validate grain, measure, sai số Decimal.
  - Toàn bộ các callback IDs (trang này có 23 callbacks với 66 Inputs và 69 Outputs).
  - Logic tạo version mới của template (`RECON_TEMPLATE_VERSION`).

## Preserve Contracts

- Khi sửa template đang Active, hệ thống phải tự sinh bản nháp (draft version) theo đúng spec 03.
- Nút "Dry-run" phải kiểm tra lấy mẫu dữ liệu thật từ Oracle qua VPN và kiểm tra khớp grain.
- Dữ liệu lưu trong store phải được đồng bộ với DB khi nhấn "Lưu nháp".

## Preflight

1. `git status --short`
2. `git branch --show-current`
3. Xem ảnh baseline `template-wizard-edit-before-1366x768.png` (cuộn 1778px).
4. Chạy `pytest tests/unit/test_template_config.py tests/e2e/test_e2e_workflow.py` ghi nhận trạng thái test hiện tại.

## Implementation Steps

1. **Step 1 — Regression Test Setup**:
   - Viết `tests/e2e/test_template_wizard_regression.py` bao quát 7 kịch bản: New, Edit, Next, Back, Save Draft, Validation Error, Reload draft.
   - Chạy test đảm bảo pass trên code hiện tại trước khi chạm vào layout.
2. **Step 2 — Stepper & Shell Modernization**:
   - Bọc trang bằng `WizardShell`.
   - Chuyển `dmc.Stepper` sang kích thước compact 1 hàng.
   - Cố định footer thanh điều hướng (`tmpl-wiz-back-btn`, `tmpl-wiz-save-draft-btn`, `tmpl-wiz-next-btn`).
3. **Step 3 — Steps Internal Scroll Optimization**:
   - Tối ưu bước 2 (Nguồn DB): SQL Editor và cột lọc co giãn nội bộ.
   - Tối ưu bước 3 (Mapping): Bảng mapping cột và cấu hình sai số cuộn nội bộ trong panel.
   - Tối ưu bước 4 (Dry-run): Bảng kết quả chạy thử nghiệm cuộn nội bộ.
4. **Step 4 — No-scroll Desktop Verification**:
   - Kiểm tra đo đạc bằng Playwright tại 1366×768: `scrollHeight <= innerHeight` (triệt tiêu 1778px về <= 768px).
5. **Step 5 — Chụp ảnh AFTER & Verification**:
   - Chụp cả New và Edit ở 1366×768, 1440×900, 390×844 lưu vào `artifacts/ui-migration/UI-05/`.
   - Chạy toàn bộ test regression đã viết ở Step 1.

## Bug Safety Rules

Mọi lỗi gặp phải phân loại:
- `A. PRE-EXISTING UNRELATED`: Ghi nhận, không sửa.
- `B. PRE-EXISTING BLOCKER`: Sửa tối thiểu nếu chặn wizard.
- `C. INTRODUCED BY CURRENT TASK`: Bắt buộc sửa và kèm regression test.
- `D. DISCOVERED RELATED BUG`: Chỉ sửa nếu thuộc phạm vi wizard và không đổi contract.
- `E. UNKNOWN`: DỪNG và hỏi người dùng.

## Tests

- Chạy `uv run poe lint`
- Chạy `uv run poe typecheck`
- Chạy `uv run poe test`
- Chạy `pytest tests/e2e/test_template_wizard_regression.py -v`
- Đo đạc tự động Playwright: Cả `/templates/new` và `/templates/<id>/edit` đều `document.documentElement.scrollHeight <= innerHeight` ở 1366×768.

## Visual Checks

- Thanh Stepper compact ở trên cùng hiển thị rõ 4 bước và bước đang chọn (màu xanh primary).
- Footer chân trang nằm cố định ở đáy màn hình, luôn nhìn thấy nút Quay lại / Tiếp theo / Lưu nháp mà không cần cuộn trang.
- Các bảng mapping và editor SQL nằm gọn trong khung nhìn, cuộn bên trong mượt mà.

## Acceptance Criteria

- [ ] `/templates/new` và `/templates/<id>/edit` chuyển thành công sang pattern WIZARD.
- [ ] Không có page scroll trên desktop 1366×768 (trang Edit giảm từ 1778px về <= 768px; trang New giảm từ 938px về <= 768px).
- [ ] Toàn bộ 7 kịch bản regression (New, Edit, Next, Back, Save Draft, Validation, Reload draft) đều PASS.
- [ ] Không có component ID nào bị thay đổi.
- [ ] Ảnh AFTER đã lưu tại `artifacts/ui-migration/UI-05/`.
- [ ] Toàn bộ test suite PASS.

## Files Expected To Change

- `app/ui/pages/template_wizard.py`
- `tests/e2e/test_template_wizard_regression.py` (tạo mới)

## Files Must Not Change

- `app/services/template.py`
- `app/engine/sql_builder.py`
- `app/schemas/template.py`
- `app/repo/**`

## Completion Report Format

```markdown
## UI-05 Completed

Pages migrated to Compact Wizard:
- /templates/new (WizardShell, fixed footer, scroll eliminated: 938px -> 768px)
- /templates/<id>/edit (WizardShell, fixed footer, scroll eliminated: 1778px -> 768px)

Regression tests (7/7 PASS):
- New template creation: PASS
- Edit existing template: PASS
- Next step navigation: PASS
- Back step navigation: PASS
- Autosave & Manual Save Draft: PASS
- Field validation: PASS
- Draft reload after page refresh: PASS

Screenshots:
- artifacts/ui-migration/UI-05/<page>-after-1366x768.png

Tests run:
- lint: PASS
- typecheck: PASS
- tests: PASS

STOP. Chờ người dùng chỉ định task tiếp theo.
```

## STOP Condition

Sau khi hoàn thành và test xong: **STOP**.
Chờ người dùng review và chỉ định task tiếp theo.

