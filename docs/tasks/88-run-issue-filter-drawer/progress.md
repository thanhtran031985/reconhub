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
  cuộn, 0 lỗi JS); full suite 1974 passed, 6 skipped. Commit, xuất patch,
  verify `git am` tại `bf2eafd`, giao patch.
