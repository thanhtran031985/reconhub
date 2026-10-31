# Spec 05 – Service và page Dash

Không có REST API công khai. Page Dash gọi service Python trực tiếp. Service nhận `ctx` (người dùng hiện tại), tự kiểm quyền, trả `ServiceResult`.

```python
class ServiceResult(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    code: str | None = None      # mã lỗi cố định
    message: str | None = None   # tiếng Việt có dấu
    details: dict | None = None  # vd lỗi validate theo path
```

## 1. Mã lỗi (app/schemas/errors.py)
`UNAUTHENTICATED, FORBIDDEN, VALIDATION_ERROR, NOT_FOUND, STALE_DATA,
LOGIN_FAILED, ACCOUNT_LOCKED, ACCOUNT_INACTIVE, PASSWORD_CHANGE_REQUIRED, PASSWORD_EMPTY, USERNAME_EXISTS, LAST_ADMIN,
DS_CONNECT_FAILED, DS_NOT_READ_ONLY, DS_IN_USE, DS_CURRENT_METADATA_LOCKED,
TABLE_NOT_FOUND, COLUMN_NOT_FOUND, SQL_NOT_ALLOWED, SQL_DESCRIBE_FAILED, SQL_PARAM_MISSING,
TEMPLATE_INVALID, TEMPLATE_CODE_EXISTS, TEMPLATE_NOT_ACTIVE, TEMPLATE_VERSION_LOCKED, DRY_RUN_REQUIRED,
FILE_TOO_LARGE, FILE_TYPE_NOT_ALLOWED, SHEET_NOT_FOUND, EXCEL_COLUMN_MISSING, TEMPLATE_NOT_DETECTED,
INVALID_RANGE, RANGE_TOO_LARGE, PROD_CONFIRM_REQUIRED, DUPLICATE_RUN_WARNING,
SOURCE_TIMEOUT, SOURCE_TOO_MANY_ROWS, SOURCE_QUERY_FAILED, SOURCE_CONNECTION_LOST, EXCEL_TOO_MANY_ROWS,
RUN_NOT_DONE, RUN_CANCELLED, RUN_BUSY, TEMP_DATA_PURGED, PURGE_CONFIRM_MISMATCH, MAINTENANCE_MODE,
MIGRATION_TARGET_NOT_EMPTY, MIGRATION_RUNNING, MIGRATION_COUNT_MISMATCH,
INTERNAL_ERROR`

## 2. Service

| Service | Hàm | Quyền |
|---|---|---|
| auth | `login(username, password, ip)` → ctx \| LOGIN_FAILED/ACCOUNT_LOCKED/ACCOUNT_INACTIVE; `logout`; `change_password(ctx, old, new)`; `current_ctx()`; `require_role(ctx, *roles)` | — |
| user | `list(ctx, q, role, active)`, `create(ctx, dto)` (đặt mật khẩu ban đầu, MUST_CHANGE_PW mặc định Y), `update(ctx, id, dto)` (họ tên, email, vai trò), `set_active(ctx, id, active)`, `reset_password(ctx, id, new_pw)`, `unlock(ctx, id)`, `login_log(ctx, user_id)` | AD. Không được bỏ vai trò ADMIN/khóa Admin cuối cùng (`LAST_ADMIN`) |
| data_source | `list(purpose?)`, `options(purpose)`, `create`, `update` (password rỗng = giữ), `test(id)`, `deactivate(id, force)`, `list_tables(id, schema, q)`, `list_columns(id, schema, table)` | AD (options: mọi role chạy được) |
| file | `upload`, `inspect`, `detect` | TO, AD, OP |
| template | `list`, `create`, `get`, `get_version`, `save_draft`, `validate_draft`, `describe_source`, `preview_sql`, `grain`, `dry_run`, `activate`, `clone`, `archive`, `export_json`, `import_json`, `diagram` | TO, AD (đọc: mọi role) |
| run | `precheck`, `create`, `list`, `get`, `columns`, `rows`, `row_detail`, `invalid`, `cancel`, `rerun`, `export`, `mark_checked(id, purge)` | OP, TO, AD (đọc: mọi role) |
| temp_data | `usage()`, `preview(filter)`, `purge_runs(run_ids)`, `purge_filter(filter, confirm_text)`, `purge_results(older_than_days, confirm_text)`, `purge_log()` | AD |
| metadata_migration | `precheck`, `start`, `status`, `list`, `delete_old_sqlite(id, confirm_name)` | AD |
| issue [GĐ3] | `list`, `update`, `bulk_update`, `reasons` | OP, TO, AD |
| dashboard [GĐ3] | `summary(month)`, `compare_runs(a, b)` | mọi role |

Cấu trúc `columns`/`rows`:
```json
{ "keys": [{"name":"INVOICE_NO","label":"Số hóa đơn","type":"text"}],
  "measures": [{"name":"TOTAL_AMOUNT","label":"Tổng tiền","type":"number","compare":"abs_tol","tolerance":1,"main":true}],
  "statuses": [{"code":"MISMATCH","label":"Lệch giá trị","count":4,"amount":"2242000"}] }
{ "row_no": 12, "status": "MISMATCH", "key": {"INVOICE_NO":"C26TBD0031338"},
  "excel": {"TOTAL_AMOUNT":"2592000"}, "db": {"TOTAL_AMOUNT":"2430000"},
  "diff": {"TOTAL_AMOUNT":{"abs":"162000","pct":0.0667}}, "excel_row_nos": [5] }
```
Decimal giữ dạng chuỗi; UI định dạng.

## 3. Page Dash

| Path | Page module | Màn thiết kế | Quyền |
|---|---|---|---|
| `/login` | pages/login.py (+ đổi mật khẩu bắt buộc) | Screen10 | công khai |
| `/` | pages/dashboard.py | Screen01 | mọi role |
| `/templates` | pages/templates.py | Screen02 | mọi role |
| `/templates/<id>/edit` | pages/template_wizard.py | Screen03, Screen04 | TO, AD |
| `/runs/new` | pages/new_run.py | Screen05 | OP, TO, AD |
| `/runs/<id>` | pages/run_result.py | Screen06 | mọi role |
| `/runs` | pages/history.py | Screen07 | mọi role |
| `/data-sources` | pages/data_sources.py (tab Nguồn đối soát, tab Lưu trữ RECON_APP) | Screen08 | AD |
| `/users` | pages/users.py | Screen11 | AD |
| `/account` | pages/account.py (thông tin, đổi mật khẩu) | Screen10 (khối đổi mật khẩu) | mọi role |
| `/issues` | pages/issues.py [GĐ3] | Screen09 | OP, TO, AD |
| `/forbidden` | pages/forbidden.py | — | mọi role |
| `/dev/ui` | pages/dev_gallery.py (chỉ APP_ENV=dev) | Gallery | AD |

Quy tắc page:
- `MUST_CHANGE_PW='Y'` → mọi page chuyển tới `/login?step=change` cho đến khi đổi mật khẩu.
- ID component `<page>-<khối>-<tên>`; pattern-matching ID cho danh sách động.
- Wizard giữ TemplateConfig trong `dcc.Store` (memory), tự lưu nháp bằng `dcc.Interval` + so hash.
- Tiến độ run/migration: `dcc.Interval` 2 giây.
- Grid kết quả: `dag.AgGrid(rowModelType="infinite")`, `getRowsRequest` → `run.rows`.
- Upload: `dcc.Upload` (`max_size` 50MB), lưu storage ngay, Store chỉ giữ `file_id`.
- Tải file: Flask `/download/...` có kiểm quyền.
- Mermaid: `html.Pre(className="mermaid")` + clientside callback `mermaid.run`.

## 4. Flask route
`GET/POST /login` (form do Dash page render, POST qua callback gọi `auth.login` rồi set phiên), `POST /logout`, `GET /health` (DB, dialect, Alembic head), `GET /health/worker`, `GET /download/file/<file_id>` (404 có thông báo nếu đã xóa), `GET /download/export/<run_id>?scope=issues|all`.
