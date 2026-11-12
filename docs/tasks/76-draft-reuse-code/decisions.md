# Task 76 — Decisions

- D1: gặp mã đã tồn tại thì resume (dùng lại), không báo lỗi — áp
  cho cả "Lưu nháp" và "Tiếp theo" ở bước 1 luồng tạo mới, qua 1
  helper chung.
- D2: resume template dùng đúng hành vi `handle_open_edit` (lấy
  DRAFT version; không có DRAFT thì báo lỗi "không có version DRAFT,
  hãy Clone") — không tự tạo version mới, không tự clone.
- D3: nhánh `feat/76-draft-reuse-code` tách từ HEAD task 75
  (`bcc5b5c`); patch 76 áp sau patch 75.
- D4 (phát hiện khi làm): handler Lưu nháp trước đây chưa có nhánh D4
  nào — chọn báo cáo qua Select rồi bấm Lưu nháp thì `create_report`
  dính CONFLICT. Đã bổ sung nhánh D4 cho cả 2 handler (dùng lại
  report_id, chỉ tạo template).
- D5 (parent review): nhánh D4 cũng resume template đã có — chọn báo
  cáo qua Select rồi gõ mã template đã tồn tại dưới báo cáo đó thì mở
  lại template đó (DRAFT) thay vì CONFLICT; chỉ tách helper
  `_template_resume_state` dùng chung cho cả helper mã gõ tay và 2
  nhánh D4. Không có DRAFT thì lỗi như `handle_open_edit`.
- D4: luồng "Báo cáo *" Select của task 75 (đã chọn mã có sẵn,
  `state["report_id"]` có, `template_id` chưa có) KHÔNG qua helper:
  giữ nguyên hành vi cũ — dùng lại report_id, chỉ tạo template, trùng
  mã template vẫn CONFLICT. Helper chỉ chạy khi mã được gõ tay ở chế
  độ "Báo cáo mới". Hệ quả phát hiện khi làm: handler Lưu nháp trước
  đây CHƯA CÓ nhánh D4 nào (chọn báo cáo qua Select rồi bấm Lưu nháp
  thì `create_report` dính CONFLICT) — task 76 bổ sung nhánh D4 cho
  cả 2 handler, sửa luôn lỗ hổng đó.
