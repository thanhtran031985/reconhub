# Plan — 35-report-aggrid

## Câu hỏi chốt

- **Q0 — Grid nào?** AG Grid qua wrapper `data_grid` sẵn có (Fluent
  Compact, dòng 32px). Đã duyệt 10/11/2026. Bản community miễn phí đủ
  dùng (sửa ô, kéo dòng, virtualize); không cần license enterprise.
- **Q1 — Lưu khi nào?** Sửa ô và kéo-thả chỉ đổi dữ liệu local trong
  grid; persist duy nhất khi bấm "Lưu cột" (1 lần gọi `update_columns`
  với toàn bộ `rowData` theo thứ tự mới). Thống nhất với hành vi nhãn
  hiện tại (chỉ lưu khi bấm Lưu). Xóa cột giữ nguyên: xóa ngay qua
  service rồi tải lại `rowData`.
- **Q2 — Nút Xóa từng dòng?** Không dùng cell renderer tùy chỉnh. Dùng
  chọn dòng (`rowSelection="single"`) + nút "Xóa cột đã chọn" trên thanh
  công cụ grid. Đổi UX nhỏ so với nút X mỗi dòng, nhưng chuẩn AgGrid và
  tránh renderer tùy chỉnh.
- **Q3 — Tìm kiếm?** Quick filter có sẵn của grid (ô tìm kiếm hiện tại
  nối vào prop quick filter), bỏ đoạn JS ẩn dòng.
- **Q4 — Version không phải DRAFT?** Grid `editable=False` toàn bộ khi
  version không phải DRAFT (khóa sửa ngay trên UI thay vì chỉ chặn ở
  service như hiện tại).
- **Q5 — Kéo-thả tham số?** Không đổi. `drag_drop_reporting.js` chỉ bỏ
  phần cột; phần tham số giữ nguyên.

## Các bước

| Bước | Nội dung | Kiểm chứng |
| --- | --- | --- |
| 0 | Task + nhánh `feat/35-report-aggrid` từ `ec71e4c`, viết plan | Dashboard regen |
| 1 | Rà grid bước 4 + API dash-ag-grid (editor, rowDrag, quick filter, selection) | Ghi chú trong plan |
| 2 | Grid AgGrid thay `_render_step4_rows` + nối "Lưu cột" theo `rowData` | Test page xanh |
| 3 | Xóa cột đã chọn + Khôi phục thứ tự + tìm kiếm + dọn JS cột/tbody ẩn | Test page xanh |
| 4 | Kiểm chứng cuối (typecheck, lint, full suite, Playwright grid nhiều cột) + xuất patch | Patch `git am` sạch |

## Rủi ro

- `rowData` prop của dash-ag-grid phải đồng bộ về Dash sau mỗi lần sửa
  ô/kéo-thả; nếu không, "Lưu cột" sẽ đọc dữ liệu cũ. Kiểm chứng bằng
  test page + Playwright (sửa nhãn → Lưu → đọc lại DB).
- Lần đầu dùng AgGrid thật trong app: căn style Fluent, dropdown editor
  trong grid, chiều cao grid trong khung wizard (`calc(100vh - 88px)`).
- Grid nhiều cột (50–100 cột) mới là ca treo thật — Playwright phải seed
  đủ cột và đo thời gian lưu/kéo-thả.
