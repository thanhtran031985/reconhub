# Plan — 34-version-reopen

## Câu hỏi chốt

- **Q0 — Mở lại từ trạng thái nào?** ACTIVE và DRY_RUN_OK → DRAFT.
  DRAFT đã là DRAFT (báo lỗi), ARCHIVED không mở lại (đã bị thay thế).
- **Q1 — ACTIVE_VERSION_ID khi mở lại ACTIVE?** Gỡ (đặt NULL). Template
  tạm thời không có version ACTIVE cho tới khi kích hoạt lại; Viewer và
  tạo run báo "chưa kích hoạt" như template chưa active. Giữ pointer cũ
  sẽ treo (trỏ tới version DRAFT) nên không giữ.
- **Q2 — Dry-run ACTIVE đổi trạng thái không?** Không. Chỉ đọc: chạy
  query, trả rows, ghi audit, giữ nguyên ACTIVE. DRAFT/DRY_RUN_OK giữ
  nguyên hành vi cũ (thành công → DRY_RUN_OK để đủ điều kiện kích hoạt).
- **Q3 — Quyền?** Chỉ ADMIN (như `delete_report`): cổng menu
  `report_admin` + kiểm tra `is_admin`.
- **Q4 — Đặt nút ở đâu?** Chỉ bước 6 trong wizard (màn hình ACTIVE và màn
  hình DRY_RUN_OK), kèm modal xác nhận nêu rõ báo cáo sẽ tạm ngưng phục vụ
  tới khi kích hoạt lại. Không thêm vào menu 3 chấm ở danh sách (giữ phạm
  vi gọn); sau khi mở lại thì nhảy sang bước 4 (Cấu hình cột).

## Các bước

| Bước | Nội dung | Kiểm chứng |
| --- | --- | --- |
| 0 | Task + nhánh `feat/34-version-reopen` từ `ac8386b`, viết plan | Dashboard regen |
| 1 | Service `reopen_version` + dry-run ACTIVE preview + test viết trước | Test service xanh |
| 2 | UI bước 6: nút + modal + callback; page dùng status dry-run trả về | Test page xanh |
| 3 | Kiểm chứng cuối (typecheck, lint, full suite, Playwright) + xuất patch | Patch `git am` sạch |

## Rủi ro

- Mở lại ACTIVE làm báo cáo tạm ngưng phục vụ ở Viewer/Trung tâm báo cáo
  và batch (đều yêu cầu version ACTIVE). Modal xác nhận phải nêu rõ điều
  này; audit ghi `REOPEN_VERSION` để truy vết.
- `handle_dry_run` / `handle_dryrun_click` gán cứng `DRY_RUN_OK` sau
  dry-run thành công — nếu quên sửa, state wizard của version ACTIVE sẽ
  lệch khỏi DB. Service trả `status` sau dry-run, page dùng đúng giá trị đó.
