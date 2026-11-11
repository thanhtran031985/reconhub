# Tiến độ — Task 63: Modal stepper chuyển Oracle + switch thật/fake

## Bước 1 — Test-first (checklist helpers + stepper)
- [ ] Viết `tests/unit/test_migration_stepper63.py` (thấy đỏ)
- [ ] Chạy targeted test, xác nhận đỏ

## Bước 2 — Cột CHECKLIST_JSON + migration 0008
- [x] Thêm cột vào `app/db/metadata.py`
- [x] Alembic revision `0008_migration_checklist` — verify upgrade/downgrade/re-upgrade trên DB tạm (44 bảng, cột xuất hiện/biến mất/xuất hiện lại)
- [x] `uv run poe schema-introspect`, `--check` OK, drift SYNCED
- [x] Test Data Model Explorer xanh (98 pass; cập nhật 3 assert đếm: history 60→61, COLUMN_ADDED 13→14, manifest version 0007→0008)
- Lưu ý: lần chạy `alembic upgrade` đầu tiên đã chạy vào `data/recon_app.db` của clone (alembic.ini gán cứng URL này, không đọc RECON_DB_URL) — DB dev local, không phải DB người dùng; cột đã có sẵn ở đó, khớp metadata.

## Bước 3 — Module pure `app/services/migration_checklist.py`
- [x] `build_fake_checklist`, `advance_fake_checklist`, `step_status`, serialize/parse, save/load
- [x] Test pure xanh (JsonText tự parse dict — `checklist_from_json` nhận cả dict lẫn str; `save_checklist` truyền dict)

## Bước 4 — `metadata_migration.py`
- [x] Ghi checklist trong `start_migration` (6 bước, theo từng bảng + checksum + backfill)
- [x] Fix D3: `start_migration` tôn trọng kết quả precheck; D9: kiểm tra cả `set_maintenance_mode`
- [x] `run_migration_background` + registry kết quả theo run_token
- [x] `get_active_migration`, `get_migration_for_poll`; `next_steps` lưu vào checklist lúc DONE
- [x] D10: báo cáo modal đọc đúng khóa source_rows/target_rows (code cũ đọc nhầm src_rows/tgt_rows nên bảng luôn hiện 0)

## Bước 5 — UI `data_sources.py`
- [x] Modal + switch + stepper dọc + checklist
- [x] Callback mở modal (khôi phục phiên PROCESSING nếu có)
- [x] Callback "Bắt đầu" (fake: precheck thật + tick mô phỏng; real: thread nền)
- [x] Callback tick fake + poll real + cảnh báo switch
- [x] Bỏ `handle_migration_start` cũ, tái dùng bảng báo cáo

## Bước 6 — Typecheck + lint + test targeted
- [x] `uv run poe typecheck` sạch; `ruff check` sạch trên mọi file đổi (39 test task 63 + migration + page + data-model = 137 pass)
- [x] Lint toàn repo còn 1 lỗi I001 có sẵn ở tests/unit/test_export_concurrency57.py (task 57, không phải file task này) — để nguyên

## Bước 7 — Check live `check-63-migration-stepper.py`
- [x] Modal mở, fake chạy hết 6 bước, checklist đủ dòng, switch BẬT hiện cảnh báo
- [x] Quét cả console error và pageerror
- [x] (Thêm) real mode chạy thật SQLite→SQLite qua launcher patch (chỉ check script)
- [x] `~/workspace/check-63-migration-stepper.py` **29/29 PASS** (port 8109, DB riêng)
  - Modal mở, đủ 6 bước; switch mặc định TẮT không cảnh báo
  - Fake: chạy hết 6 bước (~7s), checklist đủ dòng, báo cáo mô phỏng hiện
    "Khớp SHA256" + 4 bước tiếp theo; không tạo phiên, không bật bảo trì
  - Switch BẬT hiện cảnh báo; real: DONE, CHECKLIST_JSON 6 bước done +
    next_steps, MAINTENANCE=Y, target nhận 43 bảng RECON_* có dữ liệu
    (RECON_USER 1 dòng); không console error / pageerror
  - 2 lỗi check lần đầu đều do check script (badge uppercase; label switch
    Mantine không phải `<label>` text-is) — sửa script, không đổi code
- [ ] Chưa chạy full suite (parent chạy sau review)

## Trạng thái
- ✅ xong (chờ parent review + commit + xuất patch)
