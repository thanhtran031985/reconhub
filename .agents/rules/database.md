---
trigger: glob
globs: app/db/**, app/repo/**, migrations/**, worker/**, app/services/metadata_migration.py, app/services/temp_data.py, tests/integration/**
description: Quy tắc RECON_APP trên SQLite (mặc định) và Oracle, hàng đợi, dữ liệu tạm.
---

# RECON_APP: SQLite và Oracle

- Schema theo `docs/specs/02_database_schema.md`; định nghĩa một lần ở `app/db/metadata.py`. Tên bảng/cột HOA, ≤ 30 ký tự.
- Kiểu: TypeDecorator chung. **Decimal lưu TEXT trên SQLite** (`DecimalText`), `NUMBER(38,4)` trên Oracle; không dùng REAL/float cho tiền. JSON: TEXT trên SQLite, `CLOB IS JSON` trên Oracle (`JsonText`). Thời gian: UTC naive.
- SQLite khi mở kết nối (event `connect`): `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=30000`, `synchronous=NORMAL`. File tạo mới với `auto_vacuum=INCREMENTAL`. File nằm trên ổ local (không ổ mạng, không thư mục OneDrive/SharePoint đồng bộ).
- Ghi trên SQLite: transaction ngắn; `BEGIN IMMEDIATE` cho đọc-rồi-ghi. Không giữ transaction ghi khi đang gọi Oracle hay xử lý Polars.
- Lấy job (`dialect.claim_job`): SQLite `UPDATE … WHERE RUN_ID=(SELECT … WHERE STATUS='READY' ORDER BY ENQUEUED_AT LIMIT 1) RETURNING RUN_ID` trong `BEGIN IMMEDIATE`; Oracle `SELECT … FOR UPDATE SKIP LOCKED`.
- Ghi kết quả: lô 5.000 dòng; dòng kết quả chỉ đọc khi run DONE; run FAILED xóa dòng dở.
- Alembic: SQLite `render_as_batch=True`. Revision chạy `upgrade head` 2 lần và `downgrade base` → `upgrade head` trên SQLite; trên Oracle chạy khi có biến ORACLE_TEST_APP_*.
- Xóa dữ liệu tạm (spec 04 mục 12): chỉ khi người dùng yêu cầu; xóa theo lô; SQLite `PRAGMA incremental_vacuum` sau khi xóa; ghi audit.
- Sao lưu SQLite bằng `VACUUM INTO` hoặc backup API, không copy file khi đang chạy.
- Không bao giờ tạo/xóa đối tượng trên Oracle thật ngoài schema đích của chức năng chuyển metadata do Admin chọn.
