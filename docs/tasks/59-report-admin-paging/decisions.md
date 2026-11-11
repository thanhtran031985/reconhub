# Task 59 — decisions

- D1: Phân trang danh sách chính đã có (task 29) và chạy đúng live
  (check-59-paging.py 8/8 trước khi sửa) — không viết lại. Chỉ thêm
  Select chọn cỡ trang, là phần còn thiếu so với /report-runs.
- D2: Cỡ trang 10/20/50/100, mặc định 10 (giữ hành vi cũ). Pattern
  theo `report-runs-page-size`: label "N dòng/trang", value dạng
  chuỗi, đổi cỡ trang → về trang 1, giá trị ngoài danh sách →
  mặc định 10.
- D3: Select đặt trong thanh phân trang của `render_report_list`
  (cạnh dòng "Hiển thị X – Y..."), luôn hiện kể cả khi chỉ 1 trang
  — để user đổi được cỡ trang ngay cả khi danh sách đang ngắn.
- D4: Grid cột bước 4 KHÔNG phân trang: `rowDragManaged` + payload
  lưu lấy từ toàn bộ rowData/virtualRowData; bật pagination của
  AG Grid sẽ phá kéo-thả đổi thứ tự qua trang. Dry-run bước 5 giữ
  giới hạn 10 dòng (task 36). Cả hai ngoài phạm vi.
- D5: Không đổi service `list_reports` (trả toàn bộ list) — số
  lượng báo cáo nhỏ, phân trang cắt slice ở UI như hiện tại; không
  migration, không đổi schema.
