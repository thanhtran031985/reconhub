# Kế hoạch — 06-compare-engine

### Mục tiêu
Xây dựng trọn vẹn engine so khớp và đối soát (Spec 04 mục 5–7, 10; Spec 07 mục 2):
1. `app/engine/aggregate.py`: Gộp dữ liệu theo Profile (khóa ghép chuẩn ASCII `\x1f`, `KEY_TEXT`, `sum`, `count`, `count_distinct`, `min`, `max`, `first_distinct` bắt cờ INCONSISTENT, xử lý trùng lặp DUPLICATE khi `aggregate=False`, trích xuất `__row_nos`).
2. `app/engine/compare.py`: Ghép Full Outer Join theo khóa, tính chênh lệch measures theo quy tắc làm tròn `ROUND_HALF_UP` và sai số (`exact`, `abs_tol`, `pct_tol`, `null_as`), phân loại 7 trạng thái kết quả và sắp xếp.
3. `app/engine/summary.py`: Thống kê số lượng theo từng trạng thái, tổng tiền/chênh lệch, tỷ lệ khớp, sinh metadata cột.
4. `app/engine/export.py` & `app/engine/export_styles.py`: Xuất Excel bằng XlsxWriter (Sheet Tổng hợp, sheet riêng cho từng trạng thái, định dạng khóa `@` Text giữ số 0 ở đầu, tô màu `#FDECEC` ô lệch).
5. `app/engine/pipeline.py`: Chạy pipeline trọn vẹn từ file Excel và DB fetcher/mock.
6. Hoàn thiện toàn bộ 12 Golden cases (G01–G12) và chạy benchmark 200.000 dòng.

---

### Bước 1 — Aggregate (`app/engine/aggregate.py`)
- Cài đặt `aggregate(df, profile)`:
  - Sinh khóa `__key` (ghép nối `\x1f`) và `KEY_TEXT` (ghép ` | `).
  - Tính toán các hàm gộp: `sum` (Decimal), `count`, `count_distinct`, `min`, `max`.
  - Xử lý `first_distinct`: gom danh sách giá trị phân biệt, bật cờ `is_inconsistent=True` nếu >= 2 giá trị.
  - Khi `profile.aggregate == False`: phát hiện khóa lặp bật cờ `is_duplicate=True`.
  - Trích xuất `__row_nos` và `__rows`.
- Test viết trước: `tests/unit/test_engine_aggregate.py` (Unit gộp, Golden G07 inconsistent, Golden G08 duplicate).

---

### Bước 2 — Compare (`app/engine/compare.py`)
- Cài đặt `compare(excel_agg, db_agg, profile)`:
  - Full Outer Join theo `__key`.
  - Tính `diff` cho từng measure với tiền tố `x__` và `d__`.
  - Áp dụng các so sánh: `exact`, `abs_tol`, `pct_tol`, `round` (ROUND_HALF_UP), `null_as`.
  - Phân loại 7 trạng thái chuẩn: INVALID, DUPLICATE, INCONSISTENT, MISSING_IN_DB, MISSING_IN_EXCEL, DIFF, MATCHED.
  - Sắp xếp kết quả theo độ lệch giảm dần và trạng thái.
- Test viết trước: `tests/unit/test_engine_compare.py` (Unit so sánh, Golden G10 tolerance/round/null_as).

---

### Bước 3 — Pipeline + summary (`app/engine/pipeline.py`, `app/engine/summary.py`)
- Cài đặt `app/engine/summary.py`: `build_summary`, `build_columns_metadata`.
- Cài đặt `app/engine/pipeline.py`: `run_pipeline`.
- Thiết lập các Golden cases: G01_dtp_by_invoice (184 khớp, 4 lệch, 2 thiếu DB, 2 thiếu Excel), G02, G03, G04, G05, G06, G09, G11, G12.
- Test: `tests/golden/test_golden_cases.py`.

---

### Bước 4 — Export (`app/engine/export.py`, `app/engine/export_styles.py`)
- Cài đặt xuất Excel bằng `XlsxWriter`:
  - Sheet "Tổng hợp", sheet các trạng thái lệch, sheet "Khớp", sheet "Không hợp lệ".
  - Định dạng cột khóa `@` Text, màu ô lệch `#FDECEC`.
- Test viết trước: `tests/unit/test_engine_export.py` (đọc lại file bằng openpyxl xác minh định dạng).

---

### Bước 5 — Hiệu năng sơ bộ
- Viết benchmark test 200.000 dòng (`tests/unit/test_engine_benchmark.py`).
- Đo thời gian gộp và so sánh, ghi nhận vào progress.md.
