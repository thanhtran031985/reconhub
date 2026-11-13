# Task 88 — Lọc "Đối soát & Xử lý" trên trang run + nút drawer + sửa Thành tiền "—"

## Bối cảnh

Người dùng ngày 13/11/2026 trên trang `/runs/1040`:

1. Muốn thêm filter "Đối soát & Xử lý" để tìm kiếm theo trạng thái xử lý chênh lệch.
2. Trong drawer "Chi tiết nhóm đối soát", đổi tên nút "Lưu trạng thái và ghi chú" thành
   **"Chuyển xử lý chênh lệch"**, đặt cùng hàng với tiêu đề card
   "Trạng thái đối soát & Ghi chú chênh lệch", nằm bên phải card, font và nút nhỏ lại
   giống badge.
3. Drawer hiện Thành tiền "—" cho các dòng Excel gốc #4104/#4105 của hóa đơn
   `C26TBD0100011` trong khi "Tổng hợp chỉ tiêu" ghi Excel 624.500.000.
   Đã chẩn đoán xong từ dữ liệu thật (lệnh SQLite của người dùng, 13/11/2026):
   `DATA_JSON` lưu theo **tên cột gốc trong file** (`_COL_2` = số hóa đơn,
   `_COL_3` = ngày, `_COL_17` = thành tiền: 493.500.000 + 131.000.000 = 624.500.000),
   còn drawer tra theo tên trường logic nên không khớp khóa nào.
   Các template khác nhau (BILL_VTOS, Catos, mẫu DTP...) có tên cột/tên trường khác
   nhau nên **không được hardcode bất cứ tên cột nào** cho riêng case này.

## Phạm vi (3 việc, gộp 1 task)

### (A) Filter "Đối soát & Xử lý" trên trang kết quả run

- Select mới đặt trong toolbar, cạnh ô tìm kiếm `run-res-search-input` và checkbox
  "Chỉ hiện cột lệch".
- Lựa chọn: "Tất cả" + "Chưa đối soát" + các trạng thái từ lookup `ISSUE_STATUS`
  (dùng helper sẵn có của trang `_lookup_status_options`, fallback
  `DEFAULT_ISSUE_STATUS_OPTIONS` — cùng mẫu task 85/87, không import từ
  `issues.py` vì các module trang không được import lẫn nhau).
- Đổi filter → về trang 1, giống hành vi của ô tìm kiếm và tab.

### (B) Nút drawer đổi tên + dời vị trí + thu nhỏ, hành vi lưu giữ nguyên

- Người dùng chốt ngày 14/11/2026 (bấm chọn trên options widget):
  **"Chỉ lưu như cũ (đổi tên + dời nút thôi)"** — bấm xong chỉ lưu, không mở trang khác.
- Nhãn mới: "Chuyển xử lý chênh lệch". Giữ nguyên id `drawer-save-issue-btn`,
  giữ icon `lucide:save`, size thu xuống `"xs"` cho nhỏ giống badge.
- Nút dời lên cùng hàng với tiêu đề card, phía phải (title Group thành
  `justify="space-between"`). `html.Div#drawer-save-feedback` giữ nguyên id và vẫn
  được callback lưu ghi vào; callback `handle_save_issue_from_drawer` không đổi
  hành vi (vẫn gọi `upsert_issue_for_row`, cùng thông báo phản hồi).

### (C) Sửa Thành tiền "—" trong phần "Dòng Excel gốc" của drawer

- Drawer phải tra tên cột qua **mapping riêng của từng template** (bảng B2
  "Cột Excel → Trường logic" của wizard: `field.name` → `field.excel` +
  `field.excel_aliases`): từ tên trường logic của measure/group-by suy ra tên cột
  gốc trong file rồi mới đọc trong dữ liệu tạm (`DATA_JSON`).
- Thứ tự khóa: tên cột gốc (excel/aliases) trước, tên trường logic sau, các
  fallback cũ (`TOTAL_AMOUNT`, `AMOUNT`, `INVOICE_NO`) giữ cuối cùng để các
  template mà `DATA_JSON` lưu theo tên logic (mẫu DTP) vẫn chạy như cũ.
- Chỉ sửa phần "Dòng Excel gốc" trong drawer. Không đụng lưới kết quả
  (`_resolve_grid_measures` đã đúng), không đụng phần DB, không đụng
  `header_row`/`data_start_row` của template.

## Ngoài phạm vi

- Không tạo issue tự động cho các nhóm chênh lệch lúc chạy run xong (đã đề xuất,
  người dùng chưa nhận — không làm lại).
- Không sửa toast `notify_*` toàn app (~178 chỗ), không sửa D7 task 82.
- Không db-migrate. Chỉ khởi động lại app.

## Kiểm chứng trên app thật (người dùng làm sau khi áp patch)

1. Mở `/runs/1040`: filter "Đối soát & Xử lý" chọn "Chưa đối soát" → chỉ còn các
   dòng chưa có issue hoặc issue đang OPEN; chọn "Đã xử lý xong" → chỉ còn các
   dòng đã RESOLVED; đổi filter về trang 1.
2. Mở drawer một dòng "Thiếu trong DB": nút "Chuyển xử lý chênh lệch" nằm cùng
   hàng với tiêu đề card, bên phải, nhỏ giống badge; bấm lưu → issue được lưu,
   feedback hiện như cũ.
3. Drawer nhóm `2026-04-29 11:00:45 | C26TBD0100011`: 2 dòng Excel gốc hiện
   Thành tiền 493.500.000 / 131.000.000 (không còn "—"), Số hóa đơn chỉ hiện
   `C26TBD0100011`.
