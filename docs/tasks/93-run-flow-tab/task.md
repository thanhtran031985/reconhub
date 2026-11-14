# Task 93 — Tab "Luồng xử lý" trên trang run

## Vấn đề
Trang run (`/runs/<id>`) hiện chỉ có 2 tab: "Kết quả đối soát" và
"Câu lệnh SQL đối soát DB". Người dùng muốn thêm 1 tab "Luồng xử lý" để
thấy các bước xử lý của lần chạy đó diễn ra thế nào, tùy theo template
đang chạy (user duyệt mockup 14/11/2026, ví dụ run #1040 template
BILL_VTOS_BDP · profile BY_INVOICE_VTOS).

## Mục tiêu
Thêm tab thứ 3 "Luồng xử lý" vào `run-res-main-tabs`, nội dung gồm:

1. Sơ đồ 4 chặng (Dash component, không dùng Archify/Mermaid/iframe):
   Nguồn & lấy dữ liệu → Chuẩn hóa & gộp → Ghép & kết luận → Kết quả.
2. 4 thẻ chi tiết từng bước, mỗi thẻ ghi hàm Python xử lý bước đó
   (như mockup đã duyệt).
3. Dòng điểm vào: `run_executor.execute_run` →
   `pipeline.run_pipeline` (5 giai đoạn READ → FILTER → FETCH_DB →
   COMPARE → PERSIST).
4. Ô ví dụ: nhóm lệch nhất của run (dòng đầu tiên trong
   `initial_rows`, đã xếp theo độ nặng + |diff|), hiện khóa, trạng thái,
   Excel/DB/diff của measure chính.

## Ràng buộc cứng (user chốt 14/11/2026, lúc ra ngoài)
**Thêm vào không được ảnh hưởng code cũ đã test.** Tab mới là phần
thêm thuần túy: không sửa callback hiện có, không sửa 2 tab cũ, không
sửa id component hiện có, không sửa service, không đổi kiểu trả về của
helper dùng chung. Nếu phần vẽ tab mới lỗi thì chỉ tab đó hiện thông
báo lỗi, trang run vẫn mở bình thường.

## Dữ liệu (lấy từ run đang mở, không hardcode)
- Tên file: từ `run_data` (key FILENAME/file_name — xác minh trong
  `get_run`, `app/services/run_service.py`).
- Bảng + nguồn DB: từ `config["db_source"]` của version template đã
  chạy (`table`, `source_id`).
- Group_by, measures, compare/tolerance/round: từ profile đã chạy
  trong config (`config["profiles"]`, khớp `profile_code`).
- Số dòng Excel: `summary["EXCEL_ROWS_READ"]`; số nhóm/bản ghi DB:
  `summary["DB_ROWS"]`; các `CNT_MATCHED`, `CNT_MISMATCH`,
  `CNT_MISSING_IN_DB`, `CNT_MISSING_IN_EXCEL`, `CNT_INCONSISTENT`,
  `CNT_DUPLICATE`, `EXCEL_ROWS_INVALID`.
- Số liệu thiếu (run FAILED / chưa có summary) thì hiện "—".
