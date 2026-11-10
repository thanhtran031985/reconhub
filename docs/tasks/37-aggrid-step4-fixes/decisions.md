# Decisions — 37-aggrid-step4-fixes

- **Q0 (2026-11-10):** Gốc grid trống sau xóa là `getRowId="id"` dạng
  chuỗi không hoạt động (callback trả undefined mọi dòng). Sửa bằng dạng
  function nếu prototype hết warning, không thì bỏ hẳn.
  - Kết quả prototype: dạng dict `{"function": "params.data.id"}` sửa được
    node id nhưng làm crash đồng bộ selectedRows của dash-ag-grid
    (`ge.replaceAll is not a function` — code đó gọi `.replaceAll` trên
    getRowId, chỉ nhận chuỗi), kéo theo virtualRowData không đồng bộ nên
    Lưu cột không ghi thứ tự và nút Lên/Xuống không cập nhật.
  - Dạng chuỗi bare `"id"` cũng sai: dash-ag-grid đánh giá `"id"` thành
    biểu thức `return id` → undefined.
  - Dạng chuỗi biểu thức `"params.data.id"` hoạt động (chỉ còn warning
    #25 cast số sang chuỗi, vô hại).
  - Dạng chuỗi `"params.data.id.toString()"` hoạt động và **sạch warning**:
    xóa giữ đủ dòng, chọn dòng + đổi rowData không lỗi, Lưu cột ghi đúng
    thứ tự. Đây là dạng chốt.
- **Q1 (2026-11-10):** Mũi tên chỉ đổi `rowData`, "Lưu cột" ghi chung.
- **Q2 (2026-11-10):** Footer 48px → 26px; grid `calc(100vh - 380px)`.
- **Q3 (2026-11-10):** Next bước 1 chỉ toast khi thật sự ghi DB.
  Gốc toast oan: mã nhóm đã lưu là "FIN" không nằm trong
  CATEGORY_OPTIONS (FINANCE/ACCOUNTING/OPERATIONS) nên Select trống và
  mỗi lần Next lại "đổi" nhóm thành FINANCE. Sửa bằng
  `_category_options_for` giữ mã đã lưu làm option phụ (vừa hết toast oan,
  vừa không đổi ngầm dữ liệu).
- **Q4 (2026-11-10):** Hàng/Cột tab 3: `hideControls` + `textAlign center`
  + `lineHeight 22px`, Group `wrap="nowrap"`, w 38 → 34.
