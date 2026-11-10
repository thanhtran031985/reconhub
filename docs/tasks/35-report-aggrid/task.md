# 35-report-aggrid — Thay grid cột bước 4 bằng AG Grid (hết treo trang)

- Ngày tạo: 2026-11-10
- Giai đoạn: GĐ3
- Phụ thuộc: 21, 24, 33, 34
- Nhánh git: feat/35-report-aggrid (rẽ từ `ec71e4c`, đỉnh `feat/34-version-reopen`)

## Mục tiêu

Thay grid cột ở bước 4 wizard (`/report-admin/<id>`) — hiện là
`html.Table` tự dựng — bằng AG Grid (`dash-ag-grid`, đã có trong
dependencies + wrapper `app/ui/components/data_grid.py`), để hết treo
trang khi lưu/kéo-thả với template nhiều cột.

## Vấn đề (phát hiện 10/11/2026, đã phân tích, chưa code)

Grid hiện tại render toàn bộ dòng × ~11 component Dash ra DOM, không có
virtualize; mỗi dòng có 3 `dmc.Select` nặng. Mỗi lần dựng lại grid (lưu,
kéo-thả, đổi bước) là block main thread — trên app thật với nhiều cột,
Chrome báo "Page Unresponsive", bấm Wait thì hồi lại (task 33 đã sửa đúng
đắn việc lưu nhãn nhưng không xử được gốc treo).

AG Grid chỉ vẽ những dòng đang nhìn thấy, cả grid là 1 component duy
nhất, kéo-thả và sửa ô là tính năng có sẵn. `dash-ag-grid 35.3.0` đã cài,
wrapper Fluent Compact đã có, chưa page nào dùng thật.

## Phạm vi

- Chỉ grid cột bước 4: `_render_step4_rows` → AgGrid (`columnDefs`,
  `rowData`), sửa ô trực tiếp (Nhãn text, Kiểu/Định dạng/Canh select,
  Rộng number, Web/Excel/Tổng checkbox), kéo-thả đổi thứ tự bằng
  `rowDrag`, tìm kiếm bằng quick filter của grid.
- Nút "Lưu cột" đọc 1 prop `rowData` duy nhất thay vì gom ~10 danh sách
  pattern-matching `ALL` (hết luôn lớp lỗi kiểu `IndexError` ở task 33).
- Bỏ phần kéo-thả cột trong `drag_drop_reporting.js` (giữ phần tham số);
  bỏ `hidden_children` tbody cột nếu không còn callback nào dùng.
- Service giữ nguyên (`update_columns`, `move_column`, `delete_column`,
  `restore_column_order` — chỉ dùng lại khi cần; thứ tự + nội dung ô
  persist chung khi bấm "Lưu cột", xem decisions Q1).
- Không đổi: bước 1–3, bước 5–6, preview cột, validation/DRAFT-only.
