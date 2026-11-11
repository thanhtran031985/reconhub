# Task 58 — decisions

- D1: Hủy giữa chừng — checkpoint hủy từ mỗi 10 batch (50.000 dòng)
  xuống mỗi batch (5.000 dòng, 1 SELECT đơn theo khóa chính, không
  đáng kể so với đọc + ghi 1 batch). Lý do: với báo cáo ~268 nghìn
  dòng chạy ~450s, checkpoint cũ để luồng đã hủy chạy thêm tới ~80s
  mới dừng, vẫn chiếm 1 slot trong nhóm 10 của worker (pool đếm
  thread, không đếm trạng thái DB).
- D2: Chốt DONE có điều kiện (`.where(STATUS.in_(("QUEUED", "RUNNING"))`)
  + kiểm tra hủy lần nữa ngay trước khi chốt. Lý do: checkpoint trong
  vòng lặp không phủ được đoạn chốt (nén ZIP + ghi DONE); hủy rơi
  vào đoạn đó bị ghi đè thành DONE. QUEUED được chấp nhận vì worker
  claim xong là RUNNING nhưng gọi trực tiếp vẫn có thể là QUEUED
  (nhiều test + đường gọi đồng bộ cũ); CANCELLED thì không thuộc cả
  hai nên không bao giờ bị ghi đè. Chỉ ghi run DONE + audit khi
  UPDATE export áp dụng được (rowcount > 0). `_fail_export` cũng
  chỉ ghi FAILED khi còn QUEUED/RUNNING (cùng lỗi ghi đè).
- D3: Nút giữ chỗ = DMC Button thật với `visibility: hidden` +
  `disabled`, không phải `<span>` trống. Lý do: cùng kích thước
  pixel với nút thật (kể cả icon), không bấm được, không chiếm tab.
  Thứ tự vị trí cố định: [Hủy/Thử lại] [Xóa] [Xuất lại] [Chạy lại].
- D4: Lọc trạng thái theo trạng thái RUN (cột Trạng thái), không
  theo trạng thái export. Service `list_report_runs` đã có tham số
  `status` từ trước — chỉ thêm UI + truyền xuống.
- D5: Run QUEUED không có export (#32/#33 trong ảnh user 17:34)
  không thuộc phạm vi task này (user chưa trả lời tạo bằng cách
  nào); giữ nguyên hành vi, hỏi lại khi báo cáo.
