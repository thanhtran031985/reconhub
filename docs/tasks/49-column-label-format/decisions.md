# Task 49 — decisions

- D1: Quy tắc "mặc định" = nhãn trong DB bằng đúng tên cột (LABEL == FIELD_NAME)
  thì hiển thị dạng Title Case; khác tên cột thì giữ nguyên (giá trị user).
  Không migration dữ liệu, không thêm cột cờ — nhận biết bằng so sánh này.
- D2: Helper `prettify_column_label` đặt ở `app/services/report_source.py`
  (cạnh `column_display_defaults`) vì cả 3 service cần nó đều import được từ
  đó mà không vòng lặp (`report_column` và `report_run` đã import
  `report_source`; `report_template` import mới cũng an toàn vì
  `report_source` không import ngược service nào).
- D3: Áp nhãn hiệu dụng ở mọi chỗ đọc nhãn hiển thị trong service
  (`_column_dict`, `_result_layout`, `load_version_detail`,
  `_version_detail`), không chỉ grid tab 4 — để tiêu đề cột nhất quán giữa
  tab 4, trình xem báo cáo và file Excel xuất ra.
- D4: "Lưu cột" lần đầu sau patch sẽ ghi nhãn Title Case thành giá trị lưu
  tường minh cho các cột chưa sửa (do gửi toàn bộ rowData); hiển thị không
  đổi. Đây là hành vi có chủ ý, không phải tác dụng phụ.
- D5: Trường hợp hiếm — 2 cột khác nhau đổi format ra cùng 1 nhãn (vd
  `ORDER_DATE` và `ORDER__DATE`) — lúc lưu vẫn báo trùng nhãn theo luật
  uniqueness hiện có; user đổi tên 1 cột là xong. Không xử lý riêng.
- D6: Helper chỉ tách theo `_` và viết hoa chữ đầu mỗi đoạn, giả định tên cột
  DB dạng UPPER_SNAKE (đường tạo cột đã `.upper()` tên). Tên không có `_`
  (vd `AMOUNT`) → `Amount`.
