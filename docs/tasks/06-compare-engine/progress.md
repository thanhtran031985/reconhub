# Tiến độ — 06-compare-engine

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Aggregate | ✅ | 2026-11-01 | 558fe62 |
| 2 | Compare | ✅ | 2026-11-01 | 4584740 |
| 3 | Pipeline + summary | ✅ | 2026-11-01 | |
| 4 | Export | ⬜ |  |  |
| 5 | Hiệu năng sơ bộ | ⬜ |  |  |

## Nhật ký
### Bước 3 — 2026-11-01 01:06
- Đã làm: Cài đặt `app/engine/summary.py` (`build_summary`, `build_columns_metadata`), `app/engine/pipeline.py` (`run_pipeline`), cập nhật `apply_profile_filters` trong `filters.py`. Viết toàn bộ 12 Golden cases (G01–G12) trong `tests/golden/test_golden_cases.py` và sinh `db.parquet` chuẩn từ `02_seed_src_test.sql`.
- Kiểm tra: `uv run pytest tests/golden/test_golden_cases.py -v` (12 passed); `uv run poe test-engine` (197 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Khớp hoàn toàn kết quả G01: 184 Khớp, 4 Lệch (3 lệch tiền, 1 lệch ngày), 2 Thiếu DB, 2 Thiếu Excel; Control Total 366.732.000 khớp chính xác.
- Việc cần người làm thủ công: Không có.

### Bước 2 — 2026-11-01 00:56
- Đã làm: Viết test `tests/unit/test_engine_compare.py` bao phủ Full Outer Join, các trạng thái chuẩn MATCHED/MISMATCH/MISSING_IN_DB/MISSING_IN_EXCEL, độ ưu tiên trạng thái (INCONSISTENT, DUPLICATE), sai số và làm tròn (Golden G10: abs_tol, pct_tol, round ROUND_HALF_UP, null_as), measure display_only và thứ tự sắp xếp. Cài đặt `app/engine/compare.py` theo Spec 04 mục 6–7.
- Kiểm tra: `uv run pytest tests/unit/test_engine_compare.py -v` (6 passed); `uv run poe test-engine` (185 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Độ ưu tiên trạng thái theo đúng Spec 00 mục 3; tính toán sai số `pct_tol` dùng `max(|a|, |b|)`.
- Việc cần người làm thủ công: Không có.

### Bước 1 — 2026-11-01 00:53
- Đã làm: Viết test `tests/unit/test_engine_aggregate.py` bao phủ các trường hợp chuẩn, đa cột khóa, cờ INCONSISTENT (Golden G07), DUPLICATE (Golden G08), các hàm gộp min/max/count_distinct, pushdown từ DB và DataFrame rỗng. Cài đặt `app/engine/aggregate.py` theo Spec 04 mục 5.
- Kiểm tra: `uv run pytest tests/unit/test_engine_aggregate.py -v` (7 passed); `uv run poe test-engine` (179 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Hỗ trợ cờ `is_db_pushdown` và cột `__CNT_DIST` để nhận diện nhất quán giữa Oracle pushdown và gộp Polars nội bộ.
- Việc cần người làm thủ công: Không có.
