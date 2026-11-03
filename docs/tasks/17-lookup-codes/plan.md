# Kế hoạch — 17-lookup-codes

## Bước 1 — Schema & Alembic Migration
**File tạo/sửa:**
- `app/db/metadata.py` — thêm `recon_lookup_type`, `recon_lookup_code`
- `migrations/versions/xxxx_add_lookup_tables.py` — Alembic revision (SQLite batch + Oracle)
- `app/services/lookup.py` — hàm `ensure_default_lookup_data()` để seed

**Test viết trước:** `tests/unit/test_lookup_service.py` — kiểm tra bảng tồn tại, seed idempotent

**Kiểm tra:** `uv run poe db-migrate && uv run pytest tests/unit/test_lookup_service.py -k seed`

## Bước 2 — Service Quản lý Lookup
**File tạo/sửa:**
- `app/services/lookup.py` — 8 hàm CRUD với `@service` decorator, phân quyền, soft-delete, `lru_cache`

**Test:** `tests/unit/test_lookup_service.py` — đủ test mọi hàm

**Kiểm tra:** `uv run pytest tests/unit/test_lookup_service.py` → 100% PASS

## Bước 3 — Giao diện `/lookups` & Sidebar
**File tạo/sửa:**
- `app/ui/pages/lookups.py` — Master–Detail 2 cột, modals Thêm/Sửa Type/Code
- `app/ui/layout/shell.py` — thêm "Danh mục Lookups" vào nhóm Cấu hình
- `tests/unit/test_page_lookups.py` — test render layout, callback

**Kiểm tra:** `uv run poe test`, `uv run poe typecheck`, `uv run poe lint`

## Rủi ro & Quyết định
- Cache `lru_cache` cần `.cache_clear()` sau mỗi write operation
- Không cần cài thêm package nào
