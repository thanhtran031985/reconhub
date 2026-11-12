# Task 74 — Progress

- 12/11/2026: user hỏi sao /reports toàn báo cáo 1 template; parent
  chẩn đoán từ code (gom theo REPORT_ID, UI thiếu luồng thêm template
  vào báo cáo có sẵn; backend create_template đã nhận report_id).
- 12/11/2026: user chốt thiết kế refined (15:48): tab 1 wizard thêm
  nút "Tạo mới template" + ô "Mã template" thành list có search, ô
  "Tên template" disable và hiện tên theo mã. User chốt form chỉ Mã +
  Tên, không migration (15:50, D2). Parent viết task.md + plan.md +
  decisions.md; triển khai sau khi task 73 xong (D3).
- 12/11/2026: triển khai (nhánh feat/74-report-add-template từ dfc58e2).
  Test đỏ trước: tests/unit/test_report_add_template74.py (15 test) —
  12 đỏ (handler/modal/render chưa có + đường lưu report-only chưa có),
  3 xanh (hợp đồng service create_template/list_templates đã có sẵn).
  Sửa assertion thứ tự list (xếp theo DISPLAY_ORDER, CODE) khi viết test.
- 12/11/2026: triển khai xong (chưa commit, chưa chạy full suite).
  Đổi app/ui/pages/report_admin.py: render_step1 (Select mã template +
  nút "Tạo mới template" khi đang sửa; ô tên disable khi đang sửa),
  handle_save_step1 (report_id có sẵn thì chỉ tạo template), handler
  mới handle_tpl_switch / handle_new_template_save, modal
  "Tạo mới template" trong layout(), 3 callback mới (toggle modal,
  lưu modal, chuyển template). Test mới
  tests/unit/test_report_add_template74.py: 15 test, 15/15 pass.
  Targeted (74 + report_admin + reports): 98 pass; ruff check sạch;
  typecheck sạch (147 file). Format: dòng task 74 sạch, drift còn lại
  ở report_admin.py là có sẵn trước task.
- Lỗi tìm bởi check live (đã sửa): callback lưu modal thiếu
  allow_duplicate=True ở Output admin-new-tpl-alert.children -> trùng
  output với callback toggle modal -> Dash frontend từ chối cả callback
  map, app không render (trang login trống). Sửa 1 từ, kiểm lại qua
  /_dash-dependencies: không còn duplicate output thật. Bài học: mọi
  Output xuất hiện ở >1 callback đều phải có allow_duplicate=True ở
  tất cả trừ một; lỗi này chỉ lộ ở live check, unit test không bắt được.
- Check live ~/workspace/check-74-add-template.py (port 8125):
  **14/14 PASS** — Select hiện DRAFT1 + liệt kê SQL1/DRAFT1, tên
  disabled; tạo SQL2 qua modal -> wizard chuyển sang SQL2, badge
  /reports 2->3; chuyển Select sang SQL2 hiện đúng template; trùng mã
  -> toast "đã tồn tại", modal ở lại mở, Hủy đóng modal; không lỗi JS.
  Lưu ý check: seed SQL1 ACTIVE-only nên phải tạo thêm DRAFT1 qua
  service mới mở được wizard (badge bắt đầu ở 2, không phải 1).
- Chưa kiểm chứng: sau khi chuyển template bằng Select, URL vẫn giữ
  /report-admin/<id cũ> (state đổi, không đổi URL) — hành vi theo plan
  (không yêu cầu đồng bộ URL); F5 sẽ về lại template theo URL cũ.
  Mermaid/nút khác không liên quan.
- Parent review (12/11/2026): diff chỉ 1 file code report_admin.py
  (+252/−25) + test mới 15 test + docs D4/D5; test 15/15 pass
  (chạy lại độc lập); check live 14/14 PASS (chạy lại độc lập);
  ruff check sạch; typecheck sạch (147 file); full suite
  **1788 passed, 6 skipped** (1773 cũ + 15 mới).
- Parent fix nhỏ: `display_order or 10` nuốt mất giá trị 0 hợp lệ
  (ge=0) → đổi sang `int(display_order) if display_order is not None
  else 10` (kèm comment); targeted test vẫn 15/15 sau fix.
- Lưu ý chưa làm: sau khi chuyển template bằng Select, URL vẫn giữ
  /report-admin/<id cũ> — F5 sẽ về lại template theo URL cũ (plan
  không yêu cầu đồng bộ URL; follow-up nếu user muốn).
