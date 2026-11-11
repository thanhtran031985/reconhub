# Task 51 — progress

## Yêu cầu (10:30 11/11/2026)
- Card span 2: Hàng/Cột rớt xuống 2 dòng; card span 3 thì không.
- User duyệt cách sửa (nhãn lên trên ô nhập + thu ô nhập) lúc 10:42.

## Bước 1 — Đo + chẩn đoán (xong, 11/11/2026)
- Script `~/workspace/measure-48.py`: cụm ngang cần 140px; card span 2
  rộng 112px ở viewport 1100 (nội dung 94px) → rớt; viewport 1440 đủ
  chỗ; 1000 thì cả span 3 cũng rớt. Thu ô 46→36 vẫn cần 118px → phải
  đổi bố cục.

## Bước 3 — Sửa + kiểm chứng (xong, 11/11/2026)
- Cụm Hàng/Cột thành 2 `dmc.Stack` dọc (nhãn trên, ô nhập dưới); ô nhập
  46→36px; lề ngang card 8→6px. Cả cụm cần 76px → vừa card span 2 tới
  viewport ~1000px; giữ `wrap="wrap"` làm lưới an toàn dưới ngưỡng đó.
- Test mới 3; typecheck 0 lỗi, lint sạch, full suite **1481 pass /
  6 skipped**.
- Playwright `~/workspace/check-51.py` **5/5**: viewport 1440/1100/
  1000 đều giữ Hàng/Cột 1 dòng cả 4 card; tăng Cột card span 2 ở
  1100 vẫn lưu được; không lỗi trang.
- Lưu ý: check-51 lần đầu báo sai card cuối rớt ở viewport 1000 — do
  phép đo 51b đổi span trong DB (2→3) làm lệch trang đo sau; đã tách
  51b sang trang riêng. Không phải lỗi app.
