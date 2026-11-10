# Plan — 37-aggrid-step4-fixes

## Câu hỏi chốt

- **Q0 — getRowId sửa kiểu nào?** Dạng function `{"function": ...}` nếu
  prototype hết warning; không thì bỏ hẳn (AG Grid tự sinh id theo index,
  xóa render lại vẫn đúng, chỉ mất giữ selection).
- **Q1 — Mũi tên lưu khi nào?** Chỉ đổi `rowData` trên grid, "Lưu cột" ghi
  chung như kéo-thả (không gọi reorder ngay).
- **Q2 — Footer thu còn bao nhiêu?** 26px (~1/2 của 48px): nút 22px,
  capsule p=2. Grid calc theo chrome thực tế 380px.
- **Q3 — Next bước 1 khi nào toast?** Chỉ toast khi thật sự ghi DB
  (tạo mới, hoặc sửa có đổi field). Không đổi → qua bước 2 im lặng.

## Các bước

| Bước | Nội dung | Kiểm chứng |
| --- | --- | --- |
| 0 | Task + nhánh `feat/37-aggrid-step4-fixes` từ `8adbeb7` | — |
| 1 | Prototype getRowId function vs bỏ hẳn | Hết warning, xóa giữ đủ dòng |
| 2 | Sửa 6 mục (grid + footer + Next bước 1 + tab 3) | Test unit xanh |
| 3 | Kiểm chứng cuối (typecheck, lint, full suite, Playwright 1366x768 + 1440x900) + xuất patch | Patch `git am` sạch |
