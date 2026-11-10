# Decisions — 35-report-aggrid

- **Q0 (2026-11-10):** Dùng AG Grid qua wrapper `data_grid` sẵn có. Bản
  community miễn phí đủ tính năng cần (sửa ô, kéo dòng, virtualize).
- **Q1 (2026-11-10):** Sửa ô + kéo-thả chỉ đổi local; persist duy nhất
  khi bấm "Lưu cột" (1 lần gọi `update_columns` với toàn bộ `rowData`).
  Xóa cột giữ nguyên xóa ngay qua service rồi tải lại `rowData`.
- **Q2 (2026-11-10):** Không dùng cell renderer tùy chỉnh cho nút Xóa.
  Chọn dòng (`rowSelection="single"`) + nút "Xóa cột đã chọn" trên thanh
  công cụ grid.
- **Q3 (2026-11-10):** Tìm kiếm dùng quick filter có sẵn của grid; bỏ
  đoạn JS ẩn dòng ở cột.
- **Q4 (2026-11-10):** Grid `editable=False` toàn bộ khi version không
  phải DRAFT.
- **Q5 (2026-11-10):** Kéo-thả tham số không đổi; chỉ bỏ phần cột trong
  `drag_drop_reporting.js`.
