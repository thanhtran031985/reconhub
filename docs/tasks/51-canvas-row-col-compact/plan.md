# Task 51 — Canvas tab 3: Hàng/Cột không rớt hàng ở card hẹp

## Bối cảnh
User (10:30 11/11/2026, kèm ảnh app thật sau patch 48): card span 2 thì
"Hàng" và "Cột" rớt xuống 2 dòng, card span 3 thì không. User hỏi cách
giữ trên 1 dòng hoặc thu nhỏ ô nhập → duyệt "Làm luôn" lúc 10:42.

## Chẩn đoán (đo bằng ~/workspace/measure-48.py)
- Cụm Hàng/Cột xếp ngang cần 140px (nhãn Hàng 24 + ô 46 + nhãn Cột 16
  + ô 46 + khoảng cách), card span 2 chỉ rộng 112px ở viewport 1100
  (nội dung 94px) → rớt. Viewport 1440 thì đủ chỗ; 1000 thì cả card
  span 3 cũng rớt.
- Chỉ thu ô nhập 46→36 vẫn cần 118px > 94px → không đủ. Phải đổi bố
  cục mới vừa.

## Cách sửa (đã duyệt)
- Mỗi cụm Hàng/Cột thành 1 cột dọc mini: nhãn (10px) ở trên, ô nhập ở
  dưới (`dmc.Stack`, gap=0). Ô nhập 46→38px, khoảng cách giữa 2 cột
  dọc 4px, lề ngang card 8→6px.
- Cả cụm chỉ cần 36+4+36 = 76px → card span 2 vừa tới viewport ~1000
  (nội dung 85px). Dưới ngưỡng đó `wrap="wrap"` còn giữ làm lưới an
  toàn (rớt chứ không tràn khỏi card).
- Đánh đổi: card cao thêm ~12px (thêm dòng nhãn).

## Các bước
1. Đo + chẩn đoán (xong).
2. Docs + test đỏ.
3. Sửa cụm Hàng/Cột.
4. Typecheck + lint + full suite + Playwright + xuất patch (không kèm
   dashboard.html theo luật mới).
