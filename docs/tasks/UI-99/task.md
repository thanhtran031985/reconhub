# TASK UI-99 — Global UI Review & Cleanup

## Status

DONE

## Dependencies

- UI-00B (Fluent Foundation)
- UI-01 (Compact Lists)
- UI-02 (Reports & Analytics)
- UI-03 (Admin Master–Detail)
- UI-04 (Configuration Master–Detail)
- UI-05 (Template Wizard)
- UI-06 (Batch & Run Wizards)
- UI-07 (System & Auth)

> [!CAUTION]
> **STRICT PREREQUISITE**:
> Task này **TUYỆT ĐỐI KHÔNG ĐƯỢC BẮT ĐẦU** khi bất kỳ task nào từ UI-01 đến UI-07 chưa hoàn thành (chưa đạt trạng thái DONE).
> Task này được chia thành 2 Phase tách biệt: **Phase A (Audit Only)** và **Phase B (Fix)**.
> Sau Phase A, AI bắt buộc phải **STOP** để người dùng review danh sách phát hiện trước khi thực hiện Phase B.

## Objective

Thực hiện rà soát nghiệm thu toàn diện toàn bộ 26 màn hình của ReconHub sau khi đã di chuyển sang Fluent Compact + Master–Detail.
Xác nhận không còn bất kỳ màn hình nào bị cuộn toàn trang (page-scroll) hoặc tràn ngang (horizontal overflow) ở desktop, loại bỏ toàn bộ CSS thừa/chết, dọn dẹp các token không sử dụng và đảm bảo tính nhất quán thẩm mỹ 100% theo `preview-fluent.html`.

## Pages

Toàn bộ 26 trang trong ứng dụng ReconHub.

## Target Pattern

Global Audit & Production Cleanup

## Read First

1. `AGENTS.md`
2. `.agents/rules/ui-dash.md`
3. `designs/tokens.json`
4. `designs/reference/preview-fluent.html`
5. Báo cáo nghiệm thu của các task UI-01 đến UI-07
6. Toàn bộ ảnh chụp BEFORE (`artifacts/ui-inventory/`) và AFTER (`artifacts/ui-migration/`)

## Allowed Scope

### Phase A — AUDIT ONLY
- Chạy kịch bản tự động Playwright quét toàn bộ 26 trang tại 3 kích thước: 1366×768, 1440×900, 390×844.
- Kiểm tra các lỗi:
  - Lệch typography (Title order, font sizes).
  - Spacing không đồng bộ (p="lg", p="xl").
  - Màu hardcode hex, rgb/rgba còn sót lại.
  - Page-scroll desktop (`scrollHeight > innerHeight`).
  - Horizontal overflow (`scrollWidth > innerWidth`).
  - Lạm dụng Modal cho form dài.
  - Trùng lặp component abstraction.
  - CSS thừa trong `app/ui/assets/custom.css`.
  - Console warning / error hoặc lỗi accessibility cơ bản.
- **Xuất bảng Issue List chi tiết và DỪNG LẠI (STOP) chờ người dùng phê duyệt**.

### Phase B — FIX (Chỉ chạy khi có lệnh `"Tiếp tục UI-99 Fix"`)
- Sửa các lỗi layout, typography, spacing đã được phê duyệt trong Phase A.
- Xóa bỏ các class CSS chết trong `app/ui/assets/custom.css`.
- Đồng bộ lại theme DMC nếu có token bổ sung (`uv run poe theme`).
- Chạy toàn bộ kiểm thử hồi quy cuối cùng.

## Forbidden Scope

- **KHÔNG tự động sửa code trong Phase A**.
- **KHÔNG thêm tính năng mới** ngoài phạm vi UI migration.
- **KHÔNG sửa logic nghiệp vụ**, database query, hay permission semantics.
- **KHÔNG sửa designs/tokens.json** trừ khi có sự đồng ý của người dùng.

## Preserve Contracts

- Toàn bộ 26 màn hình phải hoạt động bình thường, dữ liệu nạp đúng, filter và export không bị lỗi.
- Đảm bảo tương thích ngược 100% với các test suite hiện có của repository.

## Preflight

1. Xác nhận toàn bộ UI-01 → UI-07 đã chuyển sang trạng thái DONE trong `docs/tasks/UI-MIGRATION-INDEX.md`.
2. `git status --short`
3. `git branch --show-current`
4. Chạy `uv run poe test` và `uv run poe e2e`.

## Implementation Steps

### Phase A — Audit Only
1. **Step A1 — Automated Layout & Scroll Sweep**:
   Chạy Playwright đo đạc toàn bộ 26 trang tại 1366×768 và 1440×900, ghi nhận mọi vi phạm `scrollHeight > innerHeight` hoặc `scrollWidth > innerWidth`.
2. **Step A2 — Static Code & Style Sweep**:
   Quét toàn bộ thư mục `app/ui/**` tìm các hex color, inline padding hoặc component size md/lg.
3. **Step A3 — Console & Network Error Audit**:
   Lắng nghe console browser trong quá trình navigate toàn bộ các trang để tìm React key warning, 404 assets hay unhandled error.
4. **Step A4 — Xuất báo cáo Phase A & STOP**:
   Tạo bảng tổng hợp Issue List và **DỪNG LẠI**, chờ lệnh `"Tiếp tục UI-99 Fix"`.

### Phase B — Fix (Sau khi được duyệt)
5. **Step B1 — Layout & Spacing Corrections**:
   Khắc phục các lỗi spacing và scroll còn sót lại từ danh sách Phase A.
6. **Step B2 — CSS & Tokens Clean Up**:
   Xóa bỏ các selector CSS không còn sử dụng trong `app/ui/assets/custom.css`.
7. **Step B3 — Final Visual Verification & Screenshot Compare**:
   Chụp bộ ảnh so sánh cuối cùng đối chiếu với visual reference `designs/reference/preview-fluent.html`.
8. **Step B4 — Full CI Suite**:
   Chạy lint, typecheck, unit test và e2e test toàn hệ thống.

## Bug Safety Rules

Mọi lỗi gặp phải phân loại:
- `A. PRE-EXISTING UNRELATED`: Ghi nhận, không sửa.
- `B. PRE-EXISTING BLOCKER`: Sửa tối thiểu nếu chặn hoàn tất.
- `C. INTRODUCED BY CURRENT TASK`: Bắt buộc sửa và kèm regression test.
- `D. DISCOVERED RELATED BUG`: Chỉ sửa nếu được duyệt trong danh sách Phase A.
- `E. UNKNOWN`: DỪNG và hỏi người dùng.

## Tests

- `uv run poe lint`
- `uv run poe typecheck`
- `uv run poe test`
- `uv run poe e2e`
- Playwright Sweep: 100% 26 trang `document.documentElement.scrollHeight <= innerHeight` tại 1366×768 và 1440×900.

## Visual Checks

- Mọi màn hình đều mang phong cách **Fluent Compact + Master–Detail** thống nhất:
  - Header 44px viền mảnh, navbar sáng 200px/48px, mặt thẻ phẳng `withBorder`, shadow cực nhẹ `shadow="xs"`.
  - Bảng dày dữ liệu, dòng 32px, số căn phải `tabular-nums`.
  - Master–Detail mượt mà, không giật màn hình.
  - Không có bất kỳ trang nào cuộn thanh cuộn của toàn bộ trình duyệt trên desktop.

## Acceptance Criteria

- [x] Toàn bộ 26 trang đều **KHÔNG có page scroll** ở 1366×768 và 1440×900.
- [x] Không có bất kỳ lỗi tràn ngang nào trên cả desktop và mobile.
- [x] Báo cáo Phase A được xuất đầy đủ trước khi thực hiện Phase B.
- [x] Không còn class CSS thừa hoặc màu hex hardcoded trong `app/ui/**`.
- [x] `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`, `uv run poe e2e` đều XANH 100%.
- [x] Chuyển trạng thái toàn bộ backlog sang DONE.

## Files Expected To Change

- Các file trong `app/ui/` cần sửa theo danh sách duyệt Phase A.
- `app/ui/assets/custom.css` (dọn dẹp CSS chết).
- `docs/tasks/UI-MIGRATION-INDEX.md` (cập nhật trạng thái DONE).
- `docs/ui-migration.md` (bổ sung kết luận hoàn thành).

## Files Must Not Change

- `app/services/**`
- `app/db/**`
- `app/engine/**`
- `designs/**`

## Completion Report Format

```markdown
## UI-99 Completed

Phase A Audit Summary:
- Total issues detected: X
- Fixed in Phase B: X

Final Verification:
- Pages without desktop page-scroll: 26/26 (100%)
- Pages without horizontal overflow: 26/26 (100%)
- CSS cleaned: app/ui/assets/custom.css

Full Test Suite Results:
- poe lint: PASS
- poe typecheck: PASS
- poe test: PASS
- poe e2e: PASS

Migration Status:
ALL TASKS UI-00A -> UI-99 ARE NOW COMPLETED.
```

## STOP Condition

- **Sau Phase A**: **BẮT BUỘC STOP** để người dùng review danh sách lỗi.
- **Sau Phase B**: **STOP**. Toàn bộ migration hoàn tất.

