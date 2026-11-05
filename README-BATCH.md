# ReconHub v4: gói bổ sung Bộ đối soát (task 18)

Gói độc lập, không gộp với gói Lookups, không ghi đè file v4.

| File | Nội dung |
|---|---|
| docs/specs/10_batch_run.md | Spec nghiệp vụ: quyết định đã chốt, quy trình 5 bước, gộp file, chạy lại, kết quả, quyền, service, UI, hiệu năng, audit, chuyển Oracle, kiểm thử |
| docs/specs/10_batch_run_tables.md | Thiết kế 5 bảng mới + thay đổi bảng hiện có, tham chiếu vòng, claim_job có giới hạn song song |
| docs/tasks/18-batch-run/ | task.md (10 bước), progress.md, plan.md, decisions.md, _archive/ |
| designs/components/Screen13-BatchRun/ | README + preview.html (prototype đã duyệt, có hộp thoại Thêm template) |
| samples/batch/batch_def_sample.json | Bộ mẫu với template DTP |

## Tích hợp vào v4 (agent làm khi bắt đầu task 18, theo plan được duyệt)
- docs/tasks/README.md: thêm dòng `| 18 | [18-batch-run](18-batch-run/task.md) — Bộ đối soát | ⬜ | 07, 12 (13 cho bước 10) | feat/18-batch-run |`, chạy `python scripts/tasks_dashboard.py`.
- docs/PRD.md: thêm C14 Bộ đối soát, C15 Chạy bộ, C16 Kết quả lần chạy bộ (tham chiếu spec 10).
- docs/specs/02: thêm 5 bảng (tham chiếu spec 10a); spec 05: service, mã lỗi, page; spec 08: thứ tự chép.
- designs/README.md: thêm Screen13.

## Prompt cho Antigravity
Làm task 18-batch-run theo skill lam-task. Đọc task.md, spec 10, spec 10a, Screen13 và các spec v4 liên quan. Lập Implementation Plan, nêu các chỗ phải sửa bảng hiện có (EXCEL_LOAD, EXCEL_ROW, RUN) và cách migration giữ dữ liệu cũ. Chưa code khi chưa duyệt. Làm từng bước, test trước, dừng sau mỗi bước.
