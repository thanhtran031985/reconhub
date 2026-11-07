# TASK UI-06 — Batch & Run Wizards

## Status

DONE

## Dependencies

- UI-00B (Fluent Foundation)
- UI-05 (Template Wizard)

## Objective

Chuyển đổi 2 màn hình khởi chạy đối soát (`/batch-runs` và `/runs/new`) sang pattern **WIZARD** chuẩn Fluent Compact.
Tái sử dụng component `WizardShell` đã được chứng minh hiệu quả từ UI-05 (tuyệt đối không tạo WizardShell thứ hai), chuẩn hóa vùng upload file, khung chọn khoảng ngày giờ tìm kiếm (`p_from`, `p_to`), bảng tiền kiểm tra (precheck) và footer cố định không làm cuộn trang trên desktop.

> [!IMPORTANT]
> **EXECUTION POLICY**:
> AI chỉ được thực hiện task này khi người dùng chỉ định chính xác: `"Làm UI-06"`.
> Sau khi hoàn thành task này: **STOP**. Không tự động bắt đầu task tiếp theo.

## Pages

| Route | Page Module | Task Gốc Sinh Ra | Spec Liên Quan | Màn Thiết Kế Gốc |
|---|---|---|---|---|
| `/runs/new` | `app/ui/pages/new_run.py` | [10-new-run-ui](../10-new-run-ui/task.md) | [04_excel_reader.md](../../specs/04_excel_reader.md), [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen05-NewRun` |
| `/batch-runs` | `app/ui/pages/batch_run_wizard.py` | [18-batch-run](../18-batch-run/task.md) | [10_batch_run.md](../../specs/10_batch_run.md), [10_batch_run_tables.md](../../specs/10_batch_run_tables.md) | `designs/components/Screen13-BatchRun` |

## Target Pattern

**WIZARD**:
- Header: `PageHeader` (Tiêu đề + trạng thái + thông tin nguồn).
- Stepper: `WizardShell` Stepper 1 hàng compact ở đầu trang.
- Body: Vùng nội dung `flex: 1`, cuộn nội bộ:
  - Chọn template / bộ đối soát và nhập khoảng ngày giờ (`p_from`, `p_to`).
  - Upload file Excel (vùng thả file compact, tối đa 50MB).
  - Kết quả tiền kiểm tra (Precheck file, số dòng, cột bắt buộc, cảnh báo dòng ngoài khoảng).
- Footer: Thanh điều hướng cố định chân trang (Back / Tiếp theo / Khởi chạy đối soát).

## Read First

1. `AGENTS.md`
2. `.agents/rules/ui-dash.md`
3. `docs/specs/04_excel_reader.md`
4. `docs/ui-migration.md` (mục 3, 4, 10 cho UI-06)
5. Yêu cầu & nghiệp vụ gốc:
   - [10-new-run-ui/task.md](../10-new-run-ui/task.md) (Quy trình chạy đối soát đơn lẻ, upload và validate)
   - [18-batch-run/task.md](../18-batch-run/task.md) (Quy trình chạy bộ đối soát nhiều file)
6. Baseline screenshots: `artifacts/ui-inventory/runs-new-before-1366x768.png`, `batch-runs-before-1366x768.png`
7. Triển khai `WizardShell` từ UI-00B và UI-05

## Allowed Scope

- Cập nhật layout trong `app/ui/pages/new_run.py` và `app/ui/pages/batch_run_wizard.py`:
  - Áp dụng `WizardShell` đã tạo từ UI-00B / UI-05.
  - Thu gọn vùng upload file (`file_drop`): Chiều cao vừa vặn (khoảng 100–120px), icon nhỏ gọn.
  - Form nhập ngày giờ `dmc.DateTimePicker(withSeconds=True, valueFormat="DD/MM/YYYY HH:mm:ss")` xếp gọn 1 hàng kèm nút phím tắt (Hôm nay, Hôm qua, Tháng này).
  - Cố định nút điều hướng ở chân trang.
  - Đảm bảo bảng kết quả precheck có internal scroll nếu danh sách file / dòng kiểm tra dài.

## Forbidden Scope

- **KHÔNG tạo component WizardShell thứ hai**. Bắt buộc dùng lại component từ UI-00B / UI-05.
- **KHÔNG sửa logic upload file**: Cơ chế lưu file tạm vào storage và truyền `file_id` qua `dcc.Store` phải giữ nguyên.
- **KHÔNG sửa logic tiền kiểm tra**: Bắt buộc giữ nguyên kiểm tra khoảng ngày giờ (không tự động lấy min/max ngày trong file), kiểm tra đơn vị, kiểm tra dung lượng 50MB.
- **KHÔNG sửa modal xác nhận PROD**: Chạy trên Data Source PROD bắt buộc phải qua modal xác nhận theo spec.
- **KHÔNG đổi component IDs** đã liên kết với callback chạy worker.

## Preserve Contracts

- Service `run.precheck` và `run.create` giữ nguyên contract.
- Tiến độ chạy kiểm tra qua `dcc.Interval` 2 giây chuyển tiếp sang màn hình kết quả run khi hoàn tất.
- File upload được ghi nhận đầy đủ trong `RECON_FILE` và audit log.

## Preflight

1. `git status --short`
2. `git branch --show-current`
3. Xem ảnh baseline tại `artifacts/ui-inventory/` của `runs-new` và `batch-runs`.
4. Chạy `pytest tests/e2e/test_batch_run.py tests/e2e/test_e2e_workflow.py` ghi nhận baseline test.

## Implementation Steps

1. **Step 1 — New Run Wizard Refactoring (`/runs/new`)**:
   - Tích hợp `PageHeader` và `WizardShell`.
   - Thu gọn vùng upload file và form chọn khoảng ngày giờ.
   - Bảng kết quả tiền kiểm tra (Precheck summary) nằm gọn trong body có internal scroll.
   - Cố định footer chứa nút "Chạy đối soát".
2. **Step 2 — Batch Run Wizard Refactoring (`/batch-runs`)**:
   - Áp dụng `WizardShell` cho quy trình 3 bước chạy bộ đối soát.
   - Chuẩn hóa danh sách nhiều file upload cho từng template trong bộ.
   - Giữ nguyên Modal xác nhận khi chạy trên nguồn PROD.
3. **Step 3 — No-scroll Desktop Verification**:
   - Kiểm tra bằng Playwright tại 1366×768: Cả 2 trang đạt `scrollHeight <= innerHeight`.
4. **Step 4 — Chụp ảnh AFTER & Verification**:
   - Chụp cả 2 trang ở 1366×768, 1440×900, 390×844 lưu vào `artifacts/ui-migration/UI-06/`.
   - Chạy test suite e2e.

## Bug Safety Rules

Mọi lỗi gặp phải phân loại:
- `A. PRE-EXISTING UNRELATED`: Ghi nhận, không sửa.
- `B. PRE-EXISTING BLOCKER`: Sửa tối thiểu nếu chặn khởi chạy run.
- `C. INTRODUCED BY CURRENT TASK`: Bắt buộc sửa và kèm regression test.
- `D. DISCOVERED RELATED BUG`: Chỉ sửa nếu thuộc phạm vi 2 trang trên và không đổi contract.
- `E. UNKNOWN`: DỪNG và hỏi người dùng.

## Tests

- Chạy `uv run poe lint`
- Chạy `uv run poe typecheck`
- Chạy `uv run poe test`
- Chạy `pytest tests/e2e/test_batch_run.py tests/e2e/test_e2e_workflow.py`
- Đo đạc tự động Playwright: Cả 2 trang đều `document.documentElement.scrollHeight <= innerHeight` ở 1366×768.

## Visual Checks

- Vùng thả file upload gọn gàng, có icon và text hướng dẫn rõ ràng.
- Bộ chọn ngày giờ có định dạng `DD/MM/YYYY HH:mm:ss` hiển thị chuẩn giờ Việt Nam.
- Nút "Chạy đối soát" luôn nhìn thấy ở footer cố định mà không cần cuộn trang.

## Acceptance Criteria

- [ ] `/batch-runs` và `/runs/new` chuyển thành công sang pattern WIZARD.
- [ ] Tái sử dụng thành công `WizardShell` từ UI-00B / UI-05, không tạo component trùng lặp.
- [ ] Không có page scroll trên desktop 1366×768.
- [ ] Logic upload file, validate ngày giờ, tiền kiểm tra và modal PROD hoạt động chính xác.
- [ ] Ảnh AFTER đã lưu tại `artifacts/ui-migration/UI-06/`.
- [ ] Toàn bộ test suite PASS.

## Files Expected To Change

- `app/ui/pages/new_run.py`
- `app/ui/pages/batch_run_wizard.py`

## Files Must Not Change

- `app/services/run.py`
- `app/services/batch_run.py`
- `app/services/file.py`
- `worker/**`

## Completion Report Format

```markdown
## UI-06 Completed

Pages migrated to Wizard Pattern:
- /runs/new (WizardShell, compact file drop, fixed footer, no page scroll)
- /batch-runs (WizardShell 3-step, multi-file upload, no page scroll)

Screenshots:
- artifacts/ui-migration/UI-06/<page>-after-1366x768.png

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

