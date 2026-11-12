# Task 68 — Decisions

- D1: phân trang server-side qua `list_batch_runs` đã có — không đổi
  service (card hiện chỉ lấy 5 dòng đầu, không có list đầy đủ để cắt ở UI).
- D2: mặc định 10 dòng/trang, options 10/20/50/100, đổi cỡ trang → trang 1,
  giá trị lạ → mặc định 10 (mẫu task 59).
- D3: Pagination + Select ở footer tĩnh ngoài vùng thân bảng; callback chỉ
  trả thân bảng + showing + Pagination `total`/`value` (mẫu task 60).
- D4: KHÔNG import helper phân trang từ `dashboard.py` (các module trang
  Dash không được import lẫn nhau — bài học task 66); nhân bản phần tính
  toán nhỏ (tổng số trang + dòng hiển thị) ngay trong
  `batch_run_wizard.py`.
- D5: danh từ trong dòng hiển thị là "lần chạy":
  "Hiển thị 1 – 10 trong tổng số 12 lần chạy".
