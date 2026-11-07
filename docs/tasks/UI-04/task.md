# TASK UI-04 — Configuration Master–Detail

## Status

TODO

## Dependencies

- UI-00B (Fluent Foundation)
- UI-03 (Admin Master–Detail)

## Objective

Chuyển đổi 4 màn hình cấu hình chuyên sâu (`/data-sources`, `/batches/<def_id>`, `/report-admin`, `/templates/<id>/diagram`) sang pattern **MASTER_DETAIL**.
Loại bỏ 65 inline style lặp lại trong `data-sources`, khắc phục hiện tượng sơ đồ Mermaid bung chiều cao 4132px trong `template-diagram` bằng container có bounded viewport (pan/zoom), và tái cấu trúc màn hình phức tạp nhất hệ thống (`report-admin`) thành 4 phân bước tuần tự (substeps UI-04.1 → UI-04.4).

> [!IMPORTANT]
> **EXECUTION POLICY**:
> AI chỉ được thực hiện task này khi người dùng chỉ định chính xác: `"Làm UI-04"`.
> Sau khi hoàn thành task này: **STOP**. Không tự động bắt đầu task tiếp theo.

## Pages

| Route | Page Module | Task Gốc Sinh Ra | Spec Liên Quan | Màn Thiết Kế Gốc |
|---|---|---|---|---|
| `/data-sources` | `app/ui/pages/data_sources.py` | [02-data-sources](../02-data-sources/task.md), [08-app-shell-ui](../08-app-shell-ui/task.md), [13-metadata-migration](../13-metadata-migration/task.md) | [02_database_schema.md](../../specs/02_database_schema.md), [08_metadata_migration.md](../../specs/08_metadata_migration.md) | `designs/components/Screen08-DataSources` |
| `/batches/<def_id>` | `app/ui/pages/batch_def_edit.py` | [18-batch-run](../18-batch-run/task.md) | [10_batch_run.md](../../specs/10_batch_run.md), [10_batch_run_tables.md](../../specs/10_batch_run_tables.md) | `designs/components/Screen13-BatchRun` |
| `/report-admin` | `app/ui/pages/report_admin.py` | [21-reporting-core](../21-reporting-core/task.md) → [27-reporting-ui](../27-reporting-ui/task.md) | Task 21-27 (Reporting platform) | `designs/components/Screen16-DynamicReporting` |
| `/templates/<id>/diagram` | `app/ui/pages/template_diagram.py` | [09-template-wizard-ui](../09-template-wizard-ui/task.md) | [03_template_config.md](../../specs/03_template_config.md), [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen04-TemplateDiagram` |

## Target Pattern

**MASTER_DETAIL**:
- Master: Danh sách đối tượng bên trái (Data Sources, Templates con, Báo cáo cấu hình).
- Detail: Panel thuộc tính bên phải (Thông tin kết nối, Mapping cột, Cấu hình tham số & LOV).
- Template Diagram: Bounded container có controls thu phóng (Zoom In/Out/Reset), không bung trôi chiều cao trang web.

## Read First

1. `AGENTS.md`
2. `.agents/rules/ui-dash.md`
3. `docs/ui-migration.md` (mục 3, 4, 5, 8 cho UI-04)
4. Yêu cầu & nghiệp vụ gốc:
   - [02-data-sources/task.md](../02-data-sources/task.md) & [13-metadata-migration/task.md](../13-metadata-migration/task.md) (Data Sources & metadata migration)
   - [18-batch-run/task.md](../18-batch-run/task.md) (Cấu hình bộ đối soát và mapping template con)
   - [21-reporting-core/task.md](../21-reporting-core/task.md) → [27-reporting-ui/task.md](../27-reporting-ui/task.md) (Quản trị cấu hình báo cáo động)
   - [09-template-wizard-ui/task.md](../09-template-wizard-ui/task.md) (Sơ đồ diễn giải Mermaid)
5. Baseline screenshots: `artifacts/ui-inventory/data-sources-before-1366x768.png`, `batch-def-edit-before-1366x768.png`, `report-admin-before-1366x768.png`, `template-diagram-before-1366x768.png`
6. Foundation components từ UI-00B (`MasterDetailLayout`, `PageHeader`, `CommandBar`, `DataGrid`)

## Allowed Scope

- `/data-sources`:
  - Tab 1 (Nguồn đối soát): Master (Danh sách Data Source Oracle) — Detail (Form thông tin kết nối host, port, service, user, mật khẩu mã hóa Fernet, nút Test kết nối).
  - Tab 2 (Lưu trữ RECON_APP): Master (Trạng thái DB và dung lượng tạm) — Detail (Cấu hình cảnh báo và bảng lịch sử dọn dẹp).
  - Loại bỏ hoàn toàn 65 inline styles lặp lại, chuyển sang token và component chuẩn.
- `/batches/<def_id>`:
  - Header: Tên bộ, mã bộ, nút Thêm template con.
  - Master (Trái): Danh sách các template đã gán vào bộ.
  - Detail (Phải): Panel cấu hình thứ tự chạy và mapping tham số cho template con đang chọn.
- `/templates/<id>/diagram`:
  - Đặt sơ đồ Mermaid trong container `overflow: hidden`, kích thước bounded theo viewport desktop (`height: calc(100vh - 120px)`).
  - Tích hợp thanh công cụ nhỏ: Phóng to (+), Thu nhỏ (-), Khôi phục tỷ lệ (100%), Xuất SVG.
  - Triệt tiêu hoàn toàn hiện tượng trang cuộn dài 4132px.
- `/report-admin` (Phân bước đặc biệt):
  - Chia việc thực hiện thành 4 substeps (xem mục Implementation Steps).
  - Master: Danh sách cấu hình báo cáo.
  - Detail: Cấu hình thông tin chung, nguồn dữ liệu, tham số LOV và định dạng cột.

## Forbidden Scope

- **KHÔNG thay đổi logic mã hóa mật khẩu** Fernet trong `app/core/crypto.py` hoặc logic kết nối Thin Oracle.
- **KHÔNG sửa quy trình di chuyển metadata SQLite → Oracle** (`app/services/metadata_migration.py`).
- **KHÔNG đổi component IDs** quan trọng trong callback Report Admin (vì có 26 callback với 74 States).
- **KHÔNG đổi cấu trúc template versioning**.

## Preserve Contracts

- Service Data Source: `test_connection`, `create`, `update`, `sync_current_metadata_source`.
- SQL Guard kiểm tra cú pháp và bind params trong Report Admin phải giữ nguyên.
- Script render Mermaid SVG bằng clientside callback giữ nguyên cơ chế nạp.

## Preflight

1. `git status --short`
2. `git branch --show-current`
3. Xem baseline screenshots của 4 trang.
4. Chạy `pytest tests/e2e/test_batch_def.py` kiểm tra cấu hình bộ đối soát.

## Implementation Steps

1. **Step 1 — Data Sources & Storage Master–Detail (`/data-sources`)**:
   - Chuyển tab Nguồn sang Master–Detail.
   - Loại bỏ 65 inline styles lặp lại.
   - Kiểm tra: Nút Test kết nối và Lưu cấu hình hoạt động tốt.
2. **Step 2 — Batch Definition Detail (`/batches/<def_id>`)**:
   - Tái cấu trúc danh sách template con sang Master–Detail.
   - Panel chi tiết bên phải cho phép sửa thứ tự và gán tham số.
3. **Step 3 — Bounded Template Diagram (`/templates/<id>/diagram`)**:
   - Bọc khối SVG Mermaid trong container `height: 100%, overflow: hidden`.
   - Bổ sung công cụ Pan/Zoom.
   - Kiểm tra đo đạc: `scrollHeight <= innerHeight` (triệt tiêu 4132px về <= 768px).
4. **Step 4 — Report Admin Substeps (`/report-admin`)**:
   - **UI-04.1 (Shell & Master List)**: Dựng `PageHeader` và `MasterDetailLayout`, hiển thị danh sách cấu hình báo cáo ở Master. Chạy test và xác nhận.
   - **UI-04.2 (General Info & Source)**: Detail panel Tab 1 hiển thị thông tin chung, chọn kiểu nguồn (TABLE/VIEW/CUSTOM_SQL), SQL editor có syntax highlight. Chạy test và xác nhận.
   - **UI-04.3 (Parameters & LOV)**: Detail panel Tab 2 hiển thị danh sách tham số động, cấu hình LOV và layout vị trí 12 cột. Chạy test và xác nhận.
   - **UI-04.4 (Columns & Export)**: Detail panel Tab 3 hiển thị ánh xạ cột, định dạng hiển thị và cấu hình xuất Excel. Chạy test và xác nhận.
5. **Step 5 — Chụp ảnh AFTER & Verification**:
   - Chụp 4 trang ở 1366×768, 1440×900, 390×844 lưu vào `artifacts/ui-migration/UI-04/`.
   - Chạy test suite.

## Bug Safety Rules

Mọi lỗi gặp phải phân loại:
- `A. PRE-EXISTING UNRELATED`: Ghi nhận, không sửa.
- `B. PRE-EXISTING BLOCKER`: Sửa tối thiểu nếu chặn cấu hình.
- `C. INTRODUCED BY CURRENT TASK`: Bắt buộc sửa và kèm regression test.
- `D. DISCOVERED RELATED BUG`: Chỉ sửa nếu thuộc phạm vi 4 trang trên và không đổi contract.
- `E. UNKNOWN`: DỪNG và hỏi người dùng.

## Tests

- Chạy `uv run poe lint`
- Chạy `uv run poe typecheck`
- Chạy `uv run poe test`
- Chạy `pytest tests/e2e/test_batch_def.py`
- Đo đạc tự động Playwright:
  - Cả 4 trang `document.documentElement.scrollHeight <= innerHeight` tại 1366×768.
  - Cả 4 trang `document.documentElement.scrollWidth <= innerWidth` tại 1366×768.

## Visual Checks

- `/data-sources` không còn bảng thủ công xô lệch, form kết nối bên phải rõ ràng, mật khẩu ẩn `••••••••`.
- `/templates/<id>/diagram` hiển thị sơ đồ Mermaid sắc nét, vừa vặn khung hình, không làm trang web bị kéo dài.
- `/report-admin` chuyển đổi giữa các tab thuộc tính mượt mà, không giật màn hình.

## Acceptance Criteria

- [ ] `/data-sources`, `/batches/<def_id>`, `/report-admin`, `/templates/<id>/diagram` chuyển thành công sang MASTER_DETAIL.
- [ ] Không có page scroll trên desktop 1366×768 (diagram từ 4132px về <= 768px; report-admin từ 831px về <= 768px).
- [ ] 65 inline style lặp lại trong `data_sources.py` được dọn sạch hoàn toàn.
- [ ] Report Admin hoàn thành trọn vẹn cả 4 substeps UI-04.1 → UI-04.4 không làm đứt gãy 26 callbacks hiện có.
- [ ] Ảnh AFTER đã lưu tại `artifacts/ui-migration/UI-04/`.
- [ ] Toàn bộ test suite PASS.

## Files Expected To Change

- `app/ui/pages/data_sources.py`
- `app/ui/pages/batch_def_edit.py`
- `app/ui/pages/template_diagram.py`
- `app/ui/pages/report_admin.py`

## Files Must Not Change

- `app/services/data_source.py`
- `app/services/report_admin.py`
- `app/services/metadata_migration.py`
- `app/core/crypto.py`

## Completion Report Format

```markdown
## UI-04 Completed

Pages migrated to Configuration Master–Detail:
- /data-sources (Master: Sources list | Detail: Connection & Storage form; 65 inline styles cleaned)
- /batches/<def_id> (Master: Child templates | Detail: Mapping & order)
- /templates/<id>/diagram (Bounded viewport with Pan/Zoom; Scroll eliminated: 4132px -> 768px)
- /report-admin (Completed all 4 substeps UI-04.1 -> UI-04.4; 26 callbacks preserved)

Screenshots:
- artifacts/ui-migration/UI-04/<page>-after-1366x768.png

Tests run:
- lint: PASS
- typecheck: PASS
- tests: PASS
- e2e: PASS

STOP. Chờ người dùng chỉ định task tiếp theo.
```

## STOP Condition

Sau khi hoàn thành và test xong: **STOP**.
Chờ người dùng review và chỉ định task tiếp theo.

