# Task 89 — Định dạng số tiền trang kết quả run: dấu `,` hàng nghìn, `.` số lẻ

## Yêu cầu (user, 14/11/2026)
- Format lại số tiền trong page `/runs/1040`: phân tách hàng nghìn là dấu `,`,
  số lẻ là `.`. Ví dụ: `1910000` → `1,910,000`.
- Phạm vi: số tiền trên trang kết quả run (`/runs/<id>`). Các chuỗi đếm
  ("Hiển thị 1 – 50 trong tổng số 56 dòng", "1.234 dòng") KHÔNG phải số tiền,
  giữ nguyên — user chỉ nói số tiền.

## Phân tích nguyên nhân
- `fmt_num` (`app/ui/pages/run_result.py:111`) hiện dùng chuẩn tiếng Việt:
  `f"{int(num):,}".replace(",", ".")` → `1.910.000`.
- `fmt_num` chỉ được định nghĩa và dùng trong `run_result.py` (18 chỗ, toàn bộ
  là số tiền: tổng Excel/DB/chênh lệch, cột measure trên grid, drawer "Dòng
  Excel gốc"/"Dữ liệu DB", bảng diff). Không module nào khác import nó
  → đổi `fmt_num` là đổi đúng trang run, không ảnh hưởng trang khác.
- Lỗi phụ phát hiện khi đọc code: nhánh số lẻ hiện tại
  `f"{num:,.2f}".replace(",", ".")` cho ra 2 dấu chấm với số có phần nghìn
  (vd `1234.56` → `"1.234.56"`). Đổi theo chuẩn mới thì `f"{num:,.2f}"`
  dùng trực tiếp, lỗi này biến mất.

## Thay đổi
- `app/ui/pages/run_result.py::fmt_num`: bỏ `.replace(",", ".")`, dùng trực
  tiếp định dạng `,` hàng nghìn / `.` số lẻ của f-string; giữ nguyên hành vi
  `None`/`""` → `"—"`, `0` → `"0"`, số lẻ tối đa 2 chữ số và cắt số 0 thừa.
- Test mới: `tests/unit/test_run_money_format89.py` — các case trong ví dụ
  của user + biên (0, None, "", số lẻ, số âm, chuỗi không phải số).

## Không đổi
- Chuỗi đếm trên trang (meta "dòng", footer phân trang) — không phải số tiền.
- Các trang khác (viewer, issues, queue-health...) — mỗi trang có formatter
  riêng, user chỉ yêu cầu trang run.
- Không db-migrate; chỉ khởi động lại app.
