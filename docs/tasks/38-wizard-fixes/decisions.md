# Decisions — 38-wizard-fixes

- Footer thu tiếp 26px → 20px (nút 18px, chữ 10px): người dùng đã thấy
  bản 26px sau khi áp 37 và vẫn yêu cầu thu nhỏ; đo ảnh footer strip cho
  nút ~22px hiện tại ở zoom ~1,14x.
- Lưu nháp bước 3 chỉ ghi dòng có đổi; lỗi từng dòng không chặn dòng khác.
- LOV ở bảng chỉ đổi `lov_type` (giữ cấu hình đã lưu); `control_type` đổi
  theo luật của `handle_p_save_lov`. Không đụng panel LOV (nút "Lưu cấu
  hình LOV" riêng giữ nguyên).
- Canvas trả controls nhưng giữ căn giữa + nowrap; ô nới 34 → 46px.
- `handle_param_save` vẫn là dead code — không xóa, ngoài phạm vi task.
- Cảnh báo console có sẵn, không do task 38 (ghi nhận, chưa sửa):
  (1) callback menu-search `app-menu-search-input` (shell.py, task 30)
  thiếu ở layout lúc đầu; (2) tài nguyên ngoài bị proxy chặn
  (ERR_TUNNEL_CONNECTION_FAILED); (3) React warning value=null ở form
  tham số bước 5 — `render_param_control` (report_widgets.py) truyền
  `value=None` khi param chưa có giá trị. Cả 3 đều có từ trước, không
  ảnh hưởng chức năng; sửa riêng ở task follow-up nếu cần.
- Bài học: không chạy `git stash` kiểm chứng base trong lúc full suite
  đang chạy — test mới gặp code cũ gây fail giả (6 test task 38 fail ở
  lần chạy suite đầu; chạy lại sạch thì xanh).
- Phụ: `DATA_TYPE_OPTIONS` có mục SELECT sai (không phải data_type hợp lệ
  theo ParamUpdate) — đã bỏ vì đường lưu bảng mới sẽ gọi update_param và
  vấp validation nếu người dùng chọn nó; chỉ dùng ở cột Kiểu bước 3 nên
  an toàn.
