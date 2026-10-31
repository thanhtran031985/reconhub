# Tiến độ — 06-compare-engine

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Aggregate | ✅ | 2026-11-01 | |
| 2 | Compare | ⬜ |  |  |
| 3 | Pipeline + summary | ⬜ |  |  |
| 4 | Export | ⬜ |  |  |
| 5 | Hiệu năng sơ bộ | ⬜ |  |  |

## Nhật ký
### Bước 1 — 2026-11-01 00:53
- Đã làm: Viết test `tests/unit/test_engine_aggregate.py` bao phủ các trường hợp chuẩn, đa cột khóa, cờ INCONSISTENT (Golden G07), DUPLICATE (Golden G08), các hàm gộp min/max/count_distinct, pushdown từ DB và DataFrame rỗng. Cài đặt `app/engine/aggregate.py` theo Spec 04 mục 5.
- Kiểm tra: `uv run pytest tests/unit/test_engine_aggregate.py -v` (7 passed); `uv run poe test-engine` (179 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Hỗ trợ cờ `is_db_pushdown` và cột `__CNT_DIST` để nhận diện nhất quán giữa Oracle pushdown và gộp Polars nội bộ.
- Việc cần người làm thủ công: Không có.
