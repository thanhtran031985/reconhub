# Plan — 36-dryrun-limit

## Câu hỏi chốt

- **Q0 — Vì sao chậm?** COUNT toàn bộ rồi mới lấy trang. Bỏ COUNT là
  sửa gốc; chỉ giảm 100 → 10 dòng mà giữ COUNT thì vẫn chậm.
- **Q1 — Total đi đâu?** Không còn COUNT nên không biết tổng. `total=None`;
  page không dùng `total` nữa (toast + info đều bỏ). Audit ghi
  `preview_rows`.
- **Q2 — 10 dòng cứng hay theo version?** `min(10, preview_max_rows)` —
  tôn trọng version đặt nhỏ hơn 10, còn lại luôn 10.
- **Q3 — Bỏ banner nào?** Cả ba: alert cam bước 5, banner "Dry-run OK",
  banner "Xem trước ACTIVE" (cùng khe `admin-dryrun-banner`). Toast vẫn
  báo thành công, bảng kết quả vẫn hiện — đủ tín hiệu.

## Các bước

| Bước | Nội dung | Kiểm chứng |
| --- | --- | --- |
| 0 | Task + nhánh `feat/36-dryrun-limit` từ `dbcbf17` | — |
| 1 | Service: `_execute_preview` + `dry_run_version` 10 dòng, không COUNT | Test service xanh |
| 2 | Page bước 5: bỏ alert/banner/info, sửa toast, bỏ output banner | Test page xanh |
| 3 | Kiểm chứng cuối (typecheck, lint, full suite, Playwright) + xuất patch | Patch `git am` sạch |
