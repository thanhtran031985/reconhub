# Tiến độ — 17-lookup-codes

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Schema & Migration Alembic (RECON_LOOKUP_TYPE, RECON_LOOKUP_CODE, seeder dữ liệu) | ✅ | 2026-11-03 | |
| 2 | Service nghiệp vụ `app/services/lookup.py` (CRUD, cache, validation, phân quyền) | ✅ | 2026-11-03 | |
| 3 | Màn hình Quản trị `/lookups` (Master-Detail, Modals Thêm/Sửa, tích hợp Sidebar, chuẩn Screen12) | ✅ | 2026-11-03 | |

## Nhật ký
- 2026-11-02: Tạo task 17-lookup-codes từ yêu cầu quản lý danh mục trạng thái đối soát và nguyên nhân chênh lệch.
- 2026-11-03: Hoàn thành Bước 1 (Metadata + Alembic migration 0002).
- 2026-11-03: Hoàn thành Bước 2 (Service `app/services/lookup.py` + 22 unit tests pass).
- 2026-11-03: Nâng cấp và hoàn thiện Bước 3 theo nguyên mẫu thiết kế `designs/components/Screen12-Lookups/`:
  - Thêm ô tìm kiếm Loại danh mục (Master) kèm badge đếm số lượng loại.
  - Thêm Toolbar tìm kiếm mã/nhãn + Dropdown lọc trạng thái active (Detail).
  - Thêm Alert Policy động: thông báo nhóm mã cố định (closed policy) vs nhóm mở.
  - Thêm nút "Sửa loại" trên Detail header.
  - Bổ sung Footer hint giải thích cơ chế soft-delete.
  - Cập nhật unit tests `tests/unit/test_page_lookups.py` (10 tests PASS).
  - Chạy `uv run poe typecheck` (95 source files OK) và `uv run ruff check` OK.
