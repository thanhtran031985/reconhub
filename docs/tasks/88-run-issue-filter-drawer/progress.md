# Progress — Task 88

- [x] Bước 0 — Chẩn đoán: nguyên nhân Thành tiền "—" đã rõ từ dữ liệu thật
  (DATA_JSON khóa `_COL_n`, drawer tra tên logic). Filter `issue_status` đã có
  sẵn ở schema + service nhưng chưa ai dùng ở UI. Nút drawer đã chốt hành vi
  (chỉ lưu như cũ) ngày 14/11/2026.
- [x] Bước 0 — Tạo nhánh `feat/88-run-issue-filter-drawer` từ `bf2eafd`; viết
  `task.md`, `plan.md`, `decisions.md`.
- [x] Bước 1 — Test đỏ trước (service + page + drawer). Service: 1 đỏ (OPEN), 3 xanh
  giữ hành vi cũ. Page: 8 đỏ, 1 xanh (fallback tên logic vốn đúng).
- [x] Bước 2 — Filter "Đối soát & Xử lý" trên trang run (service OPEN → NULL OR OPEN;
  Select toolbar + nối callback + về trang 1; store `run-res-filter-store` giữ
  `issue_status` nên F5 vẫn giữ lựa chọn (ghi D8 decisions.md).
- [x] Bước 3 — Nút drawer đổi tên + dời + thu nhỏ (size xs, hành vi lưu không đổi).
- [x] Bước 4 — Drawer tra khóa theo mapping template (`field_excel_map` từ config).
- [x] Bước 5 — Targeted tests + typecheck/lint + live check Playwright + full suite.
  Targeted 35 xanh (13 mới). Typecheck sạch; lint chỉ còn 1 lỗi I001 có sẵn
  ở tests/unit/test_export_concurrency57.py. Live check
  ~/workspace/check-88-run-issue-filter.py (cổng 8145): PASS — S0 options đủ,
  S1 Chưa đối soát → 53 dòng, S2 Đã xử lý xong → 1 dòng, S3 đổi filter về
  trang 1, S4 nút xs cùng hàng tiêu đề + lưu được, S5 Thành tiền 493.500.000 /
  131.000.000; không cuộn ở 1366×768 + 1440×900, 0 lỗi JS.
  Full suite: 1974 passed, 6 skipped (base 1961 + 13 test mới).
- [x] Bước 6 — Parent review độc lập: diff đúng plan (D7/D8 đã ghi); targeted 75
  xanh; typecheck sạch; lint chỉ còn I001 có sẵn; live check PASS (S0–S5, không
  cuộn, 0 lỗi JS); full suite 1974 passed, 6 skipped. Commit `f0edcc8`, xuất
  patch `~/workspace/reconhub-task88.patch` (1025 dòng), verify `git am` tại
  `bf2eafd`, giao patch. User đã áp (HEAD 949a4a5).
- [x] Follow-up 14/11/2026 — Chẩn đoán: trên app thật, template khác hiện đúng
  Thành tiền/Số hóa đơn (nhóm C26TBD0157530: 1.620.000 khớp tổng), nhưng BILL_VTOS
  vẫn "—" vì `DATA_JSON` khóa `_COL_n` không giao với tên trong config; cầu nối
  là vị trí cột (khớp tuyệt đối 24/24). Người dùng duyệt "làm luôn".
- [x] Follow-up F1 — Test đỏ trước (map vị trí + map DB, drawer `_COL_n`, không hồi quy).
- [x] Follow-up F2 — Triển khai fallback vị trí + tra qua `f.db` (D9/D10; thêm D11:
  cột Số hóa đơn ưu tiên trường INVOICE_NO trước các mục group-by khác, khôi phục
  thứ tự code trước task 88).
- [x] Follow-up F3 — Targeted 80 xanh (5 test mới); typecheck sạch; lint chỉ còn
  I001 có sẵn; live check ~/workspace/check-88f-followup.py (cổng 8145): PASS —
  S0–S4 hồi quy, S5 config BILL_VTOS v4 thật → Thành tiền 493.500.000 /
  131.000.000 + Số HĐ chỉ mã (không hiện ngày _COL_3), S6 run 1041 tra tên
  logic vẫn đúng; không cuộn ở 1366×768 + 1440×900, 0 lỗi JS.
  Full suite: 1979 passed, 6 skipped (base 1974 + 5 test mới).
- [x] Follow-up F3 — Parent review độc lập: diff đúng plan (D11 đã ghi); targeted 80
  xanh; typecheck sạch; lint chỉ còn I001 có sẵn; live check PASS (S0–S6, không
  cuộn, 0 lỗi JS); full suite 1979 passed, 6 skipped. Commit, xuất patch
  `~/workspace/reconhub-task88-followup.patch`, verify `git am` tại `f0edcc8`,
  giao patch.
