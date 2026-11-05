# Spec 10a – Thiết kế bảng dữ liệu: Bộ đối soát

Kiểu trung lập theo spec 02 mục 0 (ID, STR, TEXT, JSON, TS, DEC, INT, FLAG). Tên bảng/cột HOA, ≤ 30 ký tự. Mọi bảng có `CREATED_BY STR(60)`, `CREATED_AT TS`; bảng sửa được có thêm `UPDATED_BY`, `UPDATED_AT`, `ROW_VERSION INT NOT NULL DEFAULT 1`. Thời gian UTC naive. Định nghĩa trong `app/db/metadata.py`; một Alembic revision mới `xxxx_batch_run` (không sửa revision cũ).

## 1. RECON_BATCH_DEF – Bộ đối soát

| Cột | Kiểu | Null | Ràng buộc / mặc định | Ghi chú |
|---|---|---|---|---|
| ID | ID | N | PK | |
| CODE | STR(60) | N | UQ; `^[A-Z][A-Z0-9_]{0,59}$` | Không đổi sau tạo |
| NAME | STR(200) | N | | |
| DESCRIPTION | STR(1000) | Y | | |
| STATUS | STR(10) | N | `DRAFT`, `ACTIVE`, `ARCHIVED`; mặc định `DRAFT` | Chỉ ACTIVE được chạy |
| MAX_PARALLEL_PER_DS | INT | N | 1–4, mặc định 2 | Song song mỗi Data Source |
| OWNER_ID | ID | N | FK RECON_USER(ID) | |
| CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION | | | | |

Index: `IX_BDEF_STATUS (STATUS)`.
Kích hoạt (DRAFT → ACTIVE) yêu cầu ≥ 1 mục đang hoạt động, mọi mục có mẫu tên file, không có lỗi tham số với kỳ hiện tại.

## 2. RECON_BATCH_DEF_ITEM – Template trong bộ

| Cột | Kiểu | Null | Ràng buộc / mặc định | Ghi chú |
|---|---|---|---|---|
| ID | ID | N | PK | |
| BATCH_DEF_ID | ID | N | FK RECON_BATCH_DEF(ID) ON DELETE RESTRICT | |
| TEMPLATE_ID | ID | N | FK RECON_TEMPLATE(ID) | Tham chiếu, không sao chép cấu hình |
| SEQ_NO | INT | N | ≥ 1 | Thứ tự hiển thị |
| PRIORITY | INT | N | mặc định 100 | Nhỏ chạy trước |
| PROFILE_CODE | STR(60) | Y | | NULL = profile mặc định của template |
| DATA_SOURCE_ID | ID | Y | FK RECON_DATA_SOURCE(ID) | NULL = Data Source của template version Active |
| FILE_PATTERN | STR(400) | N | không rỗng | Glob, nhiều mẫu cách `\|` |
| MULTI_FILE | FLAG | N | mặc định `N` | Cho gộp nhiều file |
| IS_REQUIRED | FLAG | N | mặc định `Y` | |
| PARAMS_OVERRIDE_JSON | JSON | Y | object `{tên: biểu thức}` | Chỉ tham số có trong template |
| IS_ACTIVE | FLAG | N | mặc định `Y` | Gỡ khỏi bộ khi đã có lần chạy → `N` |
| CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION | | | | |

Ràng buộc:
- `UQ_BDEF_ITEM_TPL (BATCH_DEF_ID, TEMPLATE_ID)` – mỗi template một lần trong một bộ (kể cả mục `IS_ACTIVE='N'`; thêm lại thì bật lại mục cũ).
- Index `IX_BDEF_ITEM_DEF (BATCH_DEF_ID, IS_ACTIVE, SEQ_NO)`.

Ví dụ `PARAMS_OVERRIDE_JSON`: `{"p_ky": "{ky.thang}", "p_from": "{ky.tu-1d}"}`.

## 3. RECON_BATCH_RUN – Lần chạy bộ

| Cột | Kiểu | Null | Ràng buộc / mặc định | Ghi chú |
|---|---|---|---|---|
| ID | ID | N | PK | |
| BATCH_DEF_ID | ID | N | FK RECON_BATCH_DEF(ID) | |
| NAME | STR(200) | N | | Mặc định "Tháng MM/YYYY" |
| PERIOD | STR(7) | N | `^\d{4}-(0[1-9]\|1[0-2])$` | `YYYY-MM` |
| PERIOD_FROM | TS | N | | Giờ VN người dùng, lưu nguyên giá trị (như RECON_RUN.P_FROM) |
| PERIOD_TO | TS | N | CK PERIOD_FROM ≤ PERIOD_TO | |
| STATUS | STR(12) | N | `DRAFT`, `RUNNING`, `DONE`, `PARTIAL`, `CANCELLED` | |
| INCLUDE_WARN | FLAG | N | mặc định `Y` | Lựa chọn lúc bấm Chạy |
| PROD_CONFIRMED_BY | STR(60) | Y | | Có Data Source PROD |
| CNT_ITEMS, CNT_DONE, CNT_FAILED, CNT_SKIPPED, CNT_NOT_RUN | INT | N | mặc định 0 | Cập nhật khi run con đổi trạng thái |
| ZIP_PATH | STR(400) | Y | | Cache file .zip |
| ZIP_RUN_SET_HASH | STR(64) | Y | | Hash danh sách CURRENT_RUN_ID lúc sinh zip |
| STARTED_AT, FINISHED_AT | TS | Y | | |
| CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION | | | | |

Index: `IX_BRUN_DEF_PERIOD (BATCH_DEF_ID, PERIOD, CREATED_AT)`, `IX_BRUN_STATUS (STATUS, CREATED_AT)`.
Không UQ theo (bộ, kỳ): cho phép nhiều lần chạy cùng kỳ, UI cảnh báo.

## 4. RECON_BATCH_RUN_ITEM – Mục trong lần chạy (snapshot)

| Cột | Kiểu | Null | Ràng buộc / mặc định | Ghi chú |
|---|---|---|---|---|
| ID | ID | N | PK | |
| BATCH_RUN_ID | ID | N | FK RECON_BATCH_RUN(ID) | |
| BATCH_DEF_ITEM_ID | ID | N | FK RECON_BATCH_DEF_ITEM(ID) | |
| TEMPLATE_ID | ID | N | | Snapshot |
| TEMPLATE_VERSION | INT | Y | | Ghi khi precheck/bấm Chạy |
| PROFILE_CODE | STR(60) | N | | Snapshot (đã giải NULL → mặc định) |
| DATA_SOURCE_ID | ID | N | FK RECON_DATA_SOURCE(ID) | Snapshot |
| SEQ_NO, PRIORITY | INT | N | | Snapshot |
| MULTI_FILE, IS_REQUIRED | FLAG | N | | Snapshot |
| STATUS | STR(12) | N | `PENDING`, `READY`, `WARN`, `ERROR`, `SKIPPED`, `NOT_RUN`, `QUEUED`, `RUNNING`, `DONE`, `FAILED` | |
| SKIP_REASON | STR(30) | Y | `NO_FILE`, `USER_SKIP`, `TEMPLATE_ARCHIVED`, `WARN_EXCLUDED`, `PRECHECK_ERROR` | |
| SKIPPED_BY | STR(60) | Y | | Khi `USER_SKIP` |
| PARAMS_RUN_OVERRIDE_JSON | JSON | Y | | Ghi đè ở bước 3 |
| PARAMS_RESOLVED_JSON | JSON | Y | | Giá trị cuối cùng, kiểu chuẩn (datetime ISO) |
| PRECHECK_JSON | JSON | Y | | `{checks:[{code,level,message}], rows, files:[{id,rows,control_total_ok}]}` |
| PRECHECK_AT | TS | Y | | |
| CURRENT_RUN_ID | ID | Y | FK RECON_RUN(ID), **deferred/không ràng buộc ở SQLite** (xem mục 7) | Run hiện hành của mục |
| ATTEMPT_NO | INT | N | mặc định 0 | Tăng mỗi lần tạo run con |
| ERROR_CODE | STR(60) | Y | | Lỗi gần nhất |
| ERROR_MSG | STR(2000) | Y | | |
| CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION | | | | |

Ràng buộc: `UQ_BRUN_ITEM (BATCH_RUN_ID, BATCH_DEF_ITEM_ID)`. Index `IX_BRUN_ITEM_RUN (BATCH_RUN_ID, STATUS, SEQ_NO)`.

## 5. RECON_BATCH_RUN_FILE – File trong lần chạy bộ

| Cột | Kiểu | Null | Ràng buộc / mặc định | Ghi chú |
|---|---|---|---|---|
| ID | ID | N | PK | |
| BATCH_RUN_ID | ID | N | FK RECON_BATCH_RUN(ID) | |
| FILE_ID | ID | N | FK RECON_FILE(ID) | Lưu theo SHA-256 như upload hiện có |
| ORIGINAL_NAME | STR(400) | N | | Tên trong lần chạy (với file từ zip: `ten.zip/duong/dan.xlsx`) |
| NORMALIZED_NAME | STR(400) | N | | Dùng để khớp mẫu |
| FROM_ZIP_FILE_ID | ID | Y | FK RECON_FILE(ID) | File zip gốc |
| BATCH_RUN_ITEM_ID | ID | Y | FK RECON_BATCH_RUN_ITEM(ID) | NULL = chưa ghép |
| MATCH_STATE | STR(12) | N | `MATCHED`, `AMBIGUOUS`, `UNMATCHED`, `IGNORED`, `REPLACED` | |
| MATCH_BY | STR(10) | Y | `PATTERN`, `HEADER`, `MANUAL` | |
| CANDIDATE_ITEM_IDS | JSON | Y | array | Khi AMBIGUOUS |
| SHEET_NAME | STR(200) | Y | | NULL = sheet theo template |
| SEQ_IN_ITEM | INT | Y | | Thứ tự gộp |
| CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT | | | | |

Ràng buộc: `UQ_BRUN_FILE_NAME (BATCH_RUN_ID, ORIGINAL_NAME)` (chặn trùng tên). Index `IX_BRUN_FILE_ITEM (BATCH_RUN_ITEM_ID, MATCH_STATE)`, `IX_BRUN_FILE_HASH (BATCH_RUN_ID, FILE_ID)` (phát hiện trùng nội dung).
`REPLACED`: file bị thay ở thao tác "Thay file", giữ lại để truy vết.

## 6. Thay đổi bảng hiện có

| Bảng | Thay đổi | Ghi chú |
|---|---|---|
| RECON_RUN | + `BATCH_RUN_ID ID NULL` FK RECON_BATCH_RUN(ID); + `BATCH_RUN_ITEM_ID ID NULL` FK RECON_BATCH_RUN_ITEM(ID) | Index `IX_RUN_BATCH (BATCH_RUN_ID, STATUS)` |
| RECON_EXCEL_LOAD | + `FILE_SET_HASH STR(64) NOT NULL`; + `SOURCE_FILES_JSON JSON NULL`; đổi UQ từ `(FILE_ID, SHEET_NAME, TEMPLATE_ID, TEMPLATE_VERSION)` sang `(FILE_SET_HASH, SHEET_NAME, TEMPLATE_ID, TEMPLATE_VERSION)`; `FILE_ID` giữ lại = file đầu tiên | Migration: `FILE_SET_HASH = sha256(SHA256 của FILE_ID)` cho dữ liệu cũ |
| RECON_EXCEL_ROW | + `SOURCE_FILE_ID ID NULL` | Biết dòng thuộc file nào khi gộp; `EXCEL_ROW_NO` là số dòng trong file đó; PK đổi sang `(LOAD_ID, SOURCE_FILE_ID, EXCEL_ROW_NO)` với `SOURCE_FILE_ID` bắt buộc sau migration (điền = FILE_ID cho dữ liệu cũ) |
| RECON_RESULT_ROW | `EXCEL_ROW_NOS` lưu dạng `[{"f":<file_id>,"r":<row>}]` khi run có > 1 file; 1 file giữ dạng cũ `[r, …]` | Không đổi schema |
| RECON_RUN_QUEUE | Không đổi | Giới hạn song song xử lý trong `dialect.claim_job` |

## 7. Tham chiếu vòng RECON_RUN ↔ RECON_BATCH_RUN_ITEM

- `RECON_RUN.BATCH_RUN_ITEM_ID` → item (FK thật).
- `RECON_BATCH_RUN_ITEM.CURRENT_RUN_ID` → run: **không khai báo FK** trên cả SQLite và Oracle (tránh vòng khi tạo/chép/xóa); service đảm bảo toàn vẹn, có test kiểm `CURRENT_RUN_ID` luôn trỏ tới run có `BATCH_RUN_ITEM_ID` = chính item.
- Khi chuyển Oracle (spec 08): chép RECON_RUN với `BATCH_RUN_ITEM_ID=NULL` → chép 3 bảng batch → cập nhật lại `BATCH_RUN_ITEM_ID` theo lô.

## 8. Lấy job có giới hạn song song (`dialect.claim_job`)

Điều kiện thêm khi chọn run READY có `BATCH_RUN_ID` không NULL:

```sql
-- SQLite (trong BEGIN IMMEDIATE); Oracle tương đương với FOR UPDATE SKIP LOCKED trên RECON_RUN_QUEUE
SELECT q.RUN_ID
FROM   RECON_RUN_QUEUE q
JOIN   RECON_RUN r ON r.ID = q.RUN_ID
LEFT JOIN RECON_BATCH_RUN_ITEM bi ON bi.ID = r.BATCH_RUN_ITEM_ID
LEFT JOIN RECON_BATCH_RUN br ON br.ID = r.BATCH_RUN_ID
LEFT JOIN RECON_BATCH_DEF bd ON bd.ID = br.BATCH_DEF_ID
WHERE  q.STATUS = 'READY'
AND   (r.BATCH_RUN_ID IS NULL OR
       (SELECT COUNT(*) FROM RECON_RUN r2
        WHERE r2.BATCH_RUN_ID = r.BATCH_RUN_ID
        AND   r2.DATA_SOURCE_ID = r.DATA_SOURCE_ID
        AND   r2.STATUS = 'RUNNING') < bd.MAX_PARALLEL_PER_DS)
ORDER BY COALESCE(bi.PRIORITY, 100), q.ENQUEUED_AT
LIMIT 1
```
Viết bằng SQLAlchemy Core trong `app/db/dialect.py`, có test cho cả hai dialect.

## 9. Seed mẫu (`samples/batch/batch_def_sample.json`)

Bộ `DOANH_THU_CUOI_THANG` gồm template DTP mẫu (spec 03) với `FILE_PATTERN='*DTP*'`, `MULTI_FILE='Y'`. Các template khác do người dùng đăng ký thật nên không seed.

## 10. Ước lượng dung lượng

20 mục × 12 kỳ/năm: `RECON_BATCH_RUN_ITEM` ~240 dòng/năm, `RECON_BATCH_RUN_FILE` ~300–600 dòng/năm. Không đáng kể so với `RECON_RESULT_ROW`; không cần partition.
