# Decisions — Task 89

## D1 — Chỉ đổi `fmt_num`, không đổi chuỗi đếm
Các chuỗi đếm trên trang run ("Hiển thị 1 – 50 trong tổng số 56 dòng",
"1.234 dòng") dùng inline `f"{n:,}".replace(",", ".")`, không phải số tiền.
User chỉ yêu cầu số tiền → giữ nguyên. Nếu user muốn đổi luôn thì task
follow-up.

## D2 — Không đổi các trang khác
`fmt_num` là hàm cục bộ của `run_result.py`, không module nào khác dùng.
Các trang khác (viewer, issues...) có formatter riêng; user chỉ yêu cầu
trang run → không đụng.

## D3 — Số lẻ giữ tối đa 2 chữ số, cắt 0 thừa
Giữ đúng hành vi cũ trừ dấu phân cách: `1234.5` → `1,234.5`,
`1234567.89` → `1,234,567.89`. Đồng thời sửa lỗi phụ của code cũ:
nhánh số lẻ cũ cho ra 2 dấu chấm (`1234.56` → `1.234.56`).
