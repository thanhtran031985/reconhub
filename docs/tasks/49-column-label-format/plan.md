# Task 49 — Nhãn cột mặc định dạng Title Case (tab 4, page report-admin)

## Bối cảnh
Người dùng (11/11/2026): tab 4 cấu hình cột — cột Nhãn mặc định đang lấy
nguyên tên cột trong database. Muốn đổi: tên DB `TRANSACTION_DATE` thì nhãn
là `Transaction Date`, `INVOICE_DATE` → `Invoice Date`; áp chung format đó
cho TẤT CẢ các cột (2 ví dụ chỉ là ví dụ). Khi user cập nhật nhãn thì lấy
giá trị của user.

## Quy tắc đã duyệt
- Nhãn mặc định = tên cột DB dạng `UPPER_SNAKE_CASE` đổi thành Title Case,
  mỗi từ cách nhau bằng khoảng trắng (`TRANSACTION_DATE` → Transaction Date,
  `ORG_CODE` → Org Code, `AMOUNT` → Amount, `CUSTOMER_NAME` → Customer Name).
- "Mặc định" nghĩa là: chỉ áp khi nhãn chưa từng được user sửa. Dấu hiệu nhận
  biết: nhãn lưu trong DB bằng đúng tên cột (`LABEL == FIELD_NAME`) → đó là
  giá trị mặc định cũ, hiển thị dạng Title Case. Nhãn đã khác tên cột → đó là
  giá trị user đặt, giữ nguyên.
- Cột mới khi phân tích nguồn thêm vào: lưu nhãn đã đổi format ngay từ đầu.

## Vị trí sửa (đã đọc code trước khi sửa)
- Helper `prettify_column_label` mới trong `app/services/report_source.py`
  (cạnh `column_display_defaults`; `report_column.py` đã import từ
  `report_source` nên không vòng lặp import; `report_run.py` cũng đã import
  từ `report_source`).
- Tạo cột: `report_source.py` apply-diff `LABEL=name` → `LABEL=prettify(name)`
  (đây là đường duy nhất tạo cột mới từ nguồn; clone version copy nguyên nhãn
  đã lưu nên không đổi).
- Hiển thị: `_column_dict` (`report_column.py`, nguồn của grid tab 4 qua
  `list_columns` + preview + `refresh_columns`) và `_result_layout`
  (layout web/excel cho Viewer/Export) dùng nhãn hiệu dụng qua helper chung
  `_effective_label`; `report_run.py:load_version_detail` và
  `report_template.py:_version_detail` cũng dùng chung để tiêu đề cột nhất
  quán mọi nơi (tránh tab 4 hiện "Transaction Date" mà báo cáo vẫn hiện
  "TRANSACTION_DATE").
- Lưu cột không đổi hành vi: "Lưu cột" gửi toàn bộ rowData (nhãn đang hiển
  thị) lên `update_columns` — lần lưu đầu sau patch sẽ ghi nhãn Title Case
  cho các cột chưa sửa thành giá trị lưu tường minh; hiển thị không đổi, và
  từ đó nhãn đó được coi là đã đặt. User sửa nhãn → lưu đúng giá trị user.

## Các bước
1. Đọc code + chốt vị trí (xong).
2. Docs + test đỏ.
3. Helper + tạo cột + nhãn hiệu dụng ở các chỗ đọc.
4. Typecheck + lint + full suite + Playwright (tab 4 hiện Transaction Date;
   sửa nhãn → lưu → tải lại vẫn là nhãn user; cột mới từ phân tích lại cũng
   Title Case) + xuất patch.
