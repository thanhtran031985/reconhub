# Task 51 — decisions

- D1: Đổi bố cục cụm Hàng/Cột từ nhãn-bên-cạnh sang nhãn-ở-trên (2 cột
  dọc mini) thay vì chỉ thu nhỏ ô nhập — đo cho thấy thu ô nhập thôi
  vẫn không vừa card span 2 ở viewport 1100.
- D2: Ô nhập 46→36px (giá trị 1–2 chữ số vẫn đọc được, nút tăng/giảm
  đè lên phải không chiếm thêm chỗ); lề ngang card 8→6px.
- D3: Giữ `wrap="wrap"` ở nhóm ngoài làm lưới an toàn cho cửa sổ rất
  hẹp (<1000px): rớt hàng chứ không tràn khỏi card.
- D4: Nhánh `feat/51-canvas-row-col-compact` từ `963abf9` (tip task 48);
  patch áp sau patch 48, không kèm `dashboard.html`.
