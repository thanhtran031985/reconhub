# Task 77 — Progress

- 12/11/2026: user báo /reports/15: tab catos Xem có dữ liệu, bấm
  sang tab vtos không load page vtos. Parent chẩn đoán từ code:
  layout() dựng form tham số một lần cho template đầu tiên; không có
  callback nào nghe `Input("viewer-tabs", "value")` (chỉ 3 chỗ dùng
  viewer-tabs: định nghĩa Tabs + State ở run + State ở export) nên
  đổi tab chỉ đổi trạng thái active của tab, form + kết quả không vẽ
  lại. Viết task.md + plan.md + decisions.md; tách nhánh
  feat/77-viewer-template-tabs từ bcc5b5c (HEAD task 75).
- 12/11/2026: triển khai xong (subagent, chưa commit, chưa chạy full suite).
  - Diff: chỉ app/ui/pages/report_viewer.py (+~100): handler thuần
    `handle_viewer_tab_switch` + callback `handle_viewer_tab_switch_click`
    (Input viewer-tabs.value; Outputs param-form.children,
    version-store.data, run-store.data [allow_duplicate],
    page-store.data [allow_duplicate], run-error.children
    [allow_duplicate]; param-form + version-store là output mới nên
    không cần cờ). Guard: prevent_initial_call + chỉ chạy khi template
    chọn khác template của version-store; rỗng/không đổi/không tìm
    thấy template -> PreventUpdate; không có ACTIVE version -> lỗi,
    giữ form cũ (slot None -> dash.no_update). Đổi tab KHÔNG tự chạy.
  - Test mới tests/unit/test_viewer_template_tabs77.py: 6 test, 6/6
    pass (đỏ trước khi sửa: AttributeError vì chưa có handler).
    Targeted (77 + page_report_viewer + badge_switch70 +
    viewer_fixes40): 66 pass. ruff check sạch; typecheck sạch
    (147 file); format: test mới sạch, drift còn lại ở report_viewer.py
    (dòng 829, 923 — code task 54 có sẵn, không phải dòng mới).
  - Check live ~/workspace/check-77-viewer-tabs.py (port 8128,
    DB/storage riêng /run/pytest-tmp/check77.*): 8/8 PASS — seed
    báo cáo 2 template ACTIVE (catos: Từ ngày/Đến ngày/App/Org;
    vtos: Từ ngày/Đến ngày/Vùng/Kênh bán); chạy catos 55 dòng; bấm
    tab vtos -> form Vùng/Kênh bán, kết quả về "Chưa chạy"; chạy
    vtos 55 dòng, run mới nhất trong DB mang TEMPLATE_ID/VERSION_ID
    của vtos; về lại catos -> form App/Org, kết quả trống; không lỗi
    JS (console error + pageerror). Lỗi seed ban đầu: `:p_from` trong
    SQL_TEXT bị SQLAlchemy hiểu là bind param -> truyền SQL qua bound
    parameter thay vì inline.
  - Không động docs/tasks/71-report-count-timeout/progress.md,
    docs/tasks/76-draft-reuse-code/, docs/tasks/dashboard.html
    (đã chạy tasks-dashboard và revert). Chưa commit, chưa chạy
    full suite (parent chạy sau).
- 12/11/2026: parent review — rà diff sạch; xác minh guard "cùng
  template" hoạt động với version detail thật (`_version_dict` có
  `template_id`); xác minh export-store cũ không dùng lại run sai
  template (`_queued_run_id_from_export_store` so khớp `values`).
  Chạy lại: targeted 222 pass (76+77 + liên quan), check-77 8/8,
  ruff + typecheck sạch. Full suite đang chạy (chung cây 76+77).
