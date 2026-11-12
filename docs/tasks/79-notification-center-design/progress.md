# Task 79 — Progress

- 12/11/2026: user yêu cầu làm theo ảnh thiết kế (NOTIFICATION-01)
  và cập nhật vào task. Parent đối chiếu ảnh vs task 78 (9 mục
  thiếu: Master–Detail, thanh lọc, nhóm theo ngày, panel chi tiết,
  footer, tab popover, công tắc tổng, menu QUẢN TRỊ, bỏ px inline);
  user xác nhận "làm đi" 21:55. Parent tạo nhánh
  feat/79-notification-center-design từ 4758088 (HEAD task 78) +
  docs task 79, giao subagent triển khai theo plan.
- 12/11/2026: subagent bắt đầu. Preflight OK: nhánh
  feat/79-notification-center-design @ 4758088; cây sạch trừ 2
  progress.md của parent (71, 78); DB dev ở 0010_notifications
  (head); đã đọc task/plan/decisions/checklist + ảnh thiết kế.
- Preflight: sync_from_code (menu_sync.py:188-204) TỰ cập nhật
  SOURCE_GROUP/SOURCE_ORDER từ code lúc khởi động app → chuyển
  menu sang QUẢN TRỊ KHÔNG cần migration (ghi D8).
- Preflight: migration 0008 dùng op.add_column trực tiếp (không
  batch mode) → mẫu cho 0011; token --size-detail-panel: 320px đã
  có trong tokens.css; dcc.Clipboard đã dùng ở 3 trang.
- Preflight: detail resolver đọc RECON_RUN (TEMPLATE_ID→
  RECON_TEMPLATE.NAME, BATCH_RUN_ID→RECON_BATCH_RUN→BATCH_DEF_ID→
  RECON_BATCH_DEF.NAME, ERROR_CODE/ERROR_MSG, STARTED_AT/
  FINISHED_AT), RECON_REPORT_RUN (REPORT_ID/TEMPLATE_ID,
  ERROR_CODE/ERROR_MESSAGE, CREATED_AT/FINISHED_AT), RECON_RPT_EXPORT
  (RUN_ID, FILE_PATH, ERROR_MESSAGE), RECON_BATCH_RUN (BATCH_DEF_ID,
  CNT_*, STARTED_AT/FINISHED_AT).
- 12/11/2026: triển khai xong (service + migration 0011 + menu +
  popover + trang Master–Detail + modal cài đặt + CSS). Test mới
  `tests/unit/test_notification_design79.py` 29 test; sửa test cũ
  theo D12/D15/D16 (test78 ordering, menu_display sidebar,
  page_data_model history 63→65, schema_inspector version 0011).
  `uv run poe schema-introspect`: manifest 45 bảng, history 65
  event (drift 0); migration 0011 đã thử upgrade/downgrade/
  upgrade lại trên DB mới (cột RELATED_* thêm/bỏ đúng).
- 12/11/2026: 3 lỗi live tìm được khi chạy check-79, đã sửa + có
  test hồi quy: (1) dòng chọn mất class gốc `notif-row` (D14);
  (2) `dcc.Clipboard` log cảnh báo React defaultProps vào console
  → đổi sang clientside copy (D13); (3) nút Mở/Sao chép render
  có điều kiện làm chết callback list khi chọn dòng SYSTEM hoặc
  list rỗng (lỗi renderer "nonexistent object ... Input") → luôn
  render, ẩn bằng display:none (D18, helper `_action_buttons`).
  (4) badge chuông không cập nhật ngay sau khi đánh dấu trên trang
  → list callback đồng bộ luôn `app-notif-indicator` (D19).
  (5) `dmc.Button` không nhận `href`, `dmc.Box` không nhận `gap`,
  `dmc.ActionIcon` không nhận `title` (D15).
- 12/11/2026: check live `~/workspace/check-79-notification-design.py`
  (cổng 8130, DB/storage riêng) **48/48 PASS**: lọc search/loại/
  đã đọc/thời gian + Làm mới; nhóm HÔM NAY/HÔM QUA/ngày cũ + giờ
  tương đối + chấm chưa đọc; panel chi tiết RPT_00001 đủ trường +
  Mở báo cáo (đánh dấu đọc + điều hướng) + sao chép (toast);
  popover tab Tất cả/Chưa đọc + mark-all + Xem tất cả; công tắc
  tổng tắt → run lỗi không sinh thông báo, bật → sinh; footer +
  badge đồng bộ; không cuộn trang 1366×768/1440×900, mobile
  xếp dọc; JS sạch (console error + pageerror). Screenshot:
  ~/workspace/check79-1366x768.png, check79-1440x900.png,
  check79-390x844.png. Lưu ý: mobile navbar AppShell là overlay
  fixed che toàn màn hình (hành vi chung của shell, ngoài scope)
  nên screenshot mobile ẩn tạm navbar để chụp layout trang.
- 12/11/2026: targeted 376 pass; ruff + ruff format --check +
  typecheck (149 file) + git diff --check sạch. Chưa chạy full
  suite (parent chạy), chưa commit (parent commit + xuất patch).
- 12/11/2026: parent review — rà diff: migration 0011 + service
  (lọc/detail/master toggle) + shell popover tabs + menu move đúng;
  D8 đã xác minh trong code (sync_from_code cập nhật SOURCE_GROUP/
  SOURCE_ORDER nên không cần migration). UTF-8 file service sạch
  ("Thời gian chạy" hiển thị mojibake trong diff chỉ là artifact).
  Sửa 4 điểm: (1) menu order 30→70 (trùng menu_admin trong nhóm
  QUẢN TRỊ; nav sort theo order, trùng là mơ hồ); (2) icon trạng
  thái variant light→filled (theo ảnh: vòng tròn đặc); (3) nút sao
  chép từ ActionIcon trơ thành Button có nhãn "Sao chép mã run";
  (4) khôi phục nút Xóa (task 78 có, D11 bỏ nhầm — không có trong
  plan): nút Xóa trong panel + modal xác nhận (modal_confirm) +
  nhánh xóa trong callback danh sách + 6 test mới.
- 12/11/2026: parent review xong — targeted 382 pass (trừ 1 fail
  nhiễu chéo có sẵn, xem D20); check live 53/53 (48 gốc + 1 nhãn nút
  sao chép + 4 bước xóa); ruff + typecheck sạch; full suite (đang
  chạy) → commit → patch.
- Hồi quy live bắt được do parent fix: modal xóa tự mở sau mỗi lần
  lọc (nút Xóa bị remount khi panel vẽ lại, callback modal thiếu
  guard n_clicks) — đã sửa + thêm test test_delete_modal_noop_on_remount.
- Screenshot nghiệm thu mới (sau parent fix): 1366×768, 1440×900,
  390×844 ở ~/workspace/check79-*.png — icon trạng thái nền đặc,
  panel có đủ 3 nút Mở/Sao chép/Xóa, mobile xếp dọc.
- Ghi nhận (ngoài scope task 79, thuộc shell): ở 390px tiêu đề
  trang bị chữ "Người vận hành" ở header shell đè nhẹ.
- 12/11/2026: full suite ✅ — `TMPDIR=/run/pytest-tmp uv run poe test`:
  1877 passed, 6 skipped, 0 failed (~4m49s) = 1841 (task 78) + 36
  mới (29 subagent + 7 parent fix).
