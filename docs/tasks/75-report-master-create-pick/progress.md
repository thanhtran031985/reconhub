# Task 75 — Progress

- 12/11/2026: user hỏi (sau khi xem bảng) "phải có chức năng tạo mã
  báo cáo, sau đó khi đăng ký template thì sẽ chọn mã báo cáo nào" —
  parent xác nhận: hiện không có chức năng tạo mã báo cáo riêng và
  đăng ký template chưa chọn được mã báo cáo. Trình plan task 75
  (tạo mã báo cáo riêng trên /reports + wizard bước 1 chọn mã báo
  cáo); user duyệt "Làm task 75 theo plan trên" (16:42). Parent viết
  task.md + plan.md + decisions.md; tách nhánh
  feat/75-report-master-create-pick từ 6c97076 (HEAD task 74).
- 12/11/2026: triển khai xong (chưa commit, chưa chạy full suite).
  Diff (nhánh feat/75-report-master-create-pick, từ 6c97076):
  + app/ui/pages/reports.py: nút "Tạo mã báo cáo" cạnh "+ Đăng ký báo
  cáo" (chỉ ADMIN) + dmc.Modal (Mã */Tên */Nhóm/ Chủ sở hữu/Mô tả;
  Nhóm dùng CATEGORY_LABELS sẵn có ở reports.py) + handler thuần
  handle_new_report_save (create_report; thành công -> đóng modal,
  toast, store thêm báo cáo với template_count 0, hub vẽ lại theo
  bộ lọc hiện tại; trùng mã -> CONFLICT, modal ở lại mở + lỗi) +
  toggle modal + callback Lưu (6 output; allow_duplicate=True ở
  tất cả trừ reports-error-area — output duy nhất của callback này).
  Modal chỉ render khi can_admin (phát hiện khi test: modal render
  cho cả operator vì title trùng text nút).
  + app/ui/pages/report_admin.py: render_step1 thêm Select "Báo cáo *"
  (chỉ luồng tạo mới; options = list_reports + "Báo cáo mới" mặc
  định); chọn báo cáo có sẵn -> state nhận report_id, các ô báo cáo
  hiện đúng giá trị và disabled (report_locked), chỉ ô template nhập
  được; lưu đi nhánh D4 task 74 (chỉ create_template, đã có sẵn).
  Handler thuần handle_report_pick (guard kiểu switch task 74; báo
  cáo không tồn tại -> _bump + lỗi) + callback handle_s1_report_pick.
  Không động luồng sửa (editing) của task 74.
- Test mới tests/unit/test_report_master_create_pick75.py: 22 test
  (modal lưu/toggle, pick/chuyển báo cáo, pick rồi lưu bước 1 chỉ tạo
  template, render bước 1, hub modal) — 22/22 pass; service
  create_report trùng mã -> CONFLICT đã có test ở
  test_reporting_services.py nên không lặp. Targeted (75 + reports +
  74 + report_admin + reporting_services): 151 pass. ruff check sạch;
  typecheck sạch (147 file). Format: reports.py + test75 sạch; drift
  còn lại ở report_admin.py là có sẵn trước task (không phải dòng mới).
  Sửa trong lúc làm: typecheck 2 lỗi do dash.no_update ở vị trí meta
  khai str -> nới annotation sang Any; test hub operator sai vì
  lambda trả về fixture function thay vì Ctx (thiếu tham số fixture).
- Check live ~/workspace/check-75-report-master-pick.py (port 8126,
  DB/storage riêng /run/pytest-tmp/check75.*): 15/15 PASS — tạo
  RPT_NEW qua modal -> badge 0; trùng mã báo cáo -> lỗi, modal ở lại
  mở; wizard mới chọn RPT_NEW -> ô báo cáo khóa + đúng giá trị, lưu
  -> bước 2, badge lên 1; trùng mã template -> lỗi, ở lại bước 1;
  chọn "Báo cáo mới" -> ô mở ra, tạo báo cáo + template như cũ;
  không lỗi JS (console error + pageerror). Lưu ý check: badge Mantine
  viết hoa qua CSS ("0 TEMPLATE") nên assert phải lower(); modal mở
  lại xóa trắng form nên bước trùng mã phải nhập cả Chủ sở hữu (bắt
  buộc) nếu không lỗi validation sẽ che lỗi trùng mã; get_by_text
  "Tạo mã báo cáo" trùng cả nút lẫn title modal -> dùng
  get_by_role("button").
- Đã chạy `uv run poe tasks-dashboard` và revert dashboard.html.
  Không động docs/tasks/71-report-count-timeout/progress.md. Không
  commit, không chạy full suite (parent chạy sau).
- Parent review (12/11/2026): diff 2 file code (reports.py +243, report_admin.py +100/−3) + test mới 22 test; test 22/22 pass (chạy lại độc lập); check live 15/15 PASS (chạy lại độc lập); ruff check + typecheck đang chạy cùng full suite.
- Parent kiểm: file reports.py UTF-8 đúng ("Tạo mã báo cáo lỗi" không bị mojibake — chỉ là hiển thị diff); nút + modal chỉ ADMIN (trong `if can_admin`); callback Lưu modal đủ 6 output khớp handler, allow_duplicate đúng quy tắc (trừ reports-error-area); guard handle_report_pick dùng state["mode"] == "wizard" (có trong _fresh_state); luồng sửa task 74 không động.
- Parent review, tiếp: ruff check sạch; typecheck sạch (147 file);
  full suite **1810 passed, 6 skipped** (1788 cũ + 22 mới).
