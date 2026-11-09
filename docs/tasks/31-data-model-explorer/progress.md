# Tiến độ — 31-data-model-explorer (DATA-MODEL-01)

Trạng thái: ⬜

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Schema Inspector + manifest/history | ✅ | 09/11/2026 |  |
| 2 | Drift comparison + CI freshness | ✅ | 09/11/2026 |  |
| 3 | Menu + route + page skeleton + permission | ⬜ |  |  |
| 4 | Schema Explorer + command bar | ⬜ |  |  |
| 5 | ER Canvas | ⬜ |  |  |
| 6 | Detail Panel + History + Drift viewer | ⬜ |  |  |
| 7 | Sync state machine + loading/empty/error | ⬜ |  |  |
| 8 | Auto-update rule + docs + visual tests + regression | ⬜ |  |  |

## Nhật ký
- 2026-11-09: Generate task DATA-MODEL-01 từ `docs/tasks/DATA-MODEL-01_PROMT.md` (2221 dòng) + prototype `designs/reference/reconhub-er-diagram.html` mà người dùng push lên nhánh `feat/30-menu-search` (commit `c624236`). Tạo nhánh `feat/31-data-model-explorer` từ `c624236`. Hồ sơ task theo convention repo: task/plan/progress/decisions/test-checklist + dòng 31 trong `docs/tasks/README.md`. Plan ở trạng thái ĐỀ XUẤT — CHƯA DUYỆT. Chỉ implement khi người dùng yêu cầu chính xác "Làm DATA-MODEL-01".
- 2026-11-09: Bước 1 xong — `app/services/schema_inspector.py` (extract model 43 bảng, inspect live DB, domain lai Core 10/Đối soát 19/Báo cáo 11/Quản trị 3, manifest + history seed từ migration, diff không fake), `scripts/schema_introspect.py` + poe task `schema-introspect`, artifact `docs/data-model/schema-manifest.json` (43 bảng, version 0006_batch_run) + `schema-history.json` (58 events: 43 TABLE_CREATED, 11 COLUMN_ADDED, 2 COLUMN_REMOVED, 2 COLUMN_CHANGED). Test `tests/unit/test_schema_inspector.py` 17 pass; ruff sạch; mypy 0 lỗi; chạy lại không ghi lại file (không churn).
- 2026-11-09: Bước 2 xong — `app/services/schema_drift.py` (`compare_schemas` đủ 10 drift type, `drift_status`, `check_live_drift` bỏ qua `alembic_version`), bước CI "Check schema manifest freshness" trong `.github/workflows/ci.yml` (dạng `uv run poe schema-introspect --check`, đã kiểm chứng poe chuyển tiếp argument). Test drift 15 pass + freshness 4 pass (tổng 3 file schema 37 pass); mô phỏng CI local: sửa tạm manifest → exit 1 + đúng message, khôi phục → exit 0; ruff sạch; mypy 0 lỗi. Phát hiện và sửa trong bước 2: thứ tự index/FK trong manifest không deterministic theo process (set iteration) — đã sắp xếp ở extract + normalize, kèm test hồi quy xuyên process.
