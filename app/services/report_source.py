"""Nguồn dữ liệu báo cáo — task 22.

Validator CUSTOM_SQL, discovery metadata Oracle (VIEW/TABLE), query builder
whitelist và diff cột/tham số khi nguồn đổi. Chỉ ADMIN (menu report_admin)
được cấu hình nguồn; chạy báo cáo (task 25) dùng hàm thuần riêng.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_rpt_column,
    recon_rpt_param,
    recon_rpt_tpl_ver,
)
from app.engine.catalog import describe_sql, list_columns, list_tables
from app.engine.sql_dialect import quote_identifier
from app.engine.sql_guard import check_report_sql
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import requires_menu
from app.services.source_conn import open_source_connection

DEFAULT_DESCRIBE_TIMEOUT_SEC = 300

# Quyền ghi khiến account không đủ điều kiện chạy báo cáo (tái dùng danh
# sách của data_source._test_oracle_connection, spec 12 §2).
_WRITE_PRIVILEGES = (
    "CREATE TABLE",
    "DROP ANY TABLE",
    "ALTER ANY TABLE",
    "INSERT ANY TABLE",
    "UPDATE ANY TABLE",
    "DELETE ANY TABLE",
)

# Map kiểu Oracle (ALL_TAB_COLUMNS / cursor.description) sang kiểu cột báo cáo.
ORACLE_TYPE_MAP: dict[str, str] = {
    "DATE": "DATE",
    "TIMESTAMP": "DATETIME",
    "TIMESTAMP WITH TIME ZONE": "DATETIME",
    "TIMESTAMP WITH LOCAL TIME ZONE": "DATETIME",
    "NUMBER": "NUMBER",
    "FLOAT": "NUMBER",
    "BINARY_FLOAT": "NUMBER",
    "BINARY_DOUBLE": "NUMBER",
    "VARCHAR2": "STRING",
    "VARCHAR": "STRING",
    "CHAR": "STRING",
    "NVARCHAR2": "STRING",
    "NCHAR": "STRING",
    "CLOB": "STRING",
    "NCLOB": "STRING",
    "LONG": "STRING",
    "BLOB": "BINARY",
    "RAW": "BINARY",
}


def map_oracle_type(oracle_type: str) -> str:
    """Map kiểu Oracle sang kiểu cột báo cáo; kiểu lạ mặc định STRING."""
    base = oracle_type.strip().upper().split("(")[0].strip()
    return ORACLE_TYPE_MAP.get(base, "STRING")


# Operator filter cho phép (khớp check constraint RECON_RPT_PARAM, task 21).
FILTER_OPERATORS = ("=", ">=", "<=", "BETWEEN", "IN", "LIKE_PREFIX", "IS_NULL")

_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")


def _validate_identifier(name: str, what: str) -> None:
    """Chặn identifier lạ (khoảng trắng, dấu nháy, dấu chấm phẩy...) — T22-06."""
    if not _IDENTIFIER_RE.match(name.strip()):
        raise ServiceError(
            ErrorCode.SQL_NOT_ALLOWED,
            f"Tên {what} không hợp lệ: {name!r}.",
        )


def _whitelist_column(name: str, whitelist: dict[str, str]) -> str:
    """Trả tên cột chuẩn (theo metadata) nếu nằm trong whitelist — T22-06."""
    canonical = whitelist.get(name.strip().upper())
    if canonical is None:
        raise ServiceError(
            ErrorCode.SQL_NOT_ALLOWED,
            f"Cột {name!r} không nằm trong danh sách cột của nguồn dữ liệu.",
        )
    return canonical


def build_report_query(
    source_type: str,
    owner: str,
    object_name: str,
    columns: list[dict[str, Any]],
    selected: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    sorts: list[dict[str, str]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Sinh SELECT cho nguồn VIEW/TABLE từ metadata đã discover (T22-03, T22-06).

    columns: whitelist metadata [{"name": ...}]. selected: cột lấy ra
    (rỗng = tất cả theo thứ tự metadata). filters: [{"column", "operator",
    "code", "value"}] — giá trị luôn bind, không nối chuỗi; filter rỗng
    (None/""/[]) bị bỏ qua. sorts: [{"column", "direction"}].
    Trả (sql, binds). CUSTOM_SQL không qua builder (dùng SQL snapshot
    của version sau validate_version_sql).
    """
    if source_type not in ("VIEW", "TABLE"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "build_report_query chỉ dùng cho nguồn VIEW/TABLE; "
            "CUSTOM_SQL dùng trực tiếp SQL snapshot của version.",
        )
    if not columns:
        raise ServiceError(
            ErrorCode.SQL_NOT_ALLOWED,
            "Nguồn dữ liệu không có cột nào trong metadata.",
        )
    _validate_identifier(owner, "schema")
    _validate_identifier(object_name, "đối tượng")
    whitelist = {str(c["name"]).upper(): str(c["name"]) for c in columns}

    if selected:
        select_cols = [_whitelist_column(c, whitelist) for c in selected]
    else:
        select_cols = [str(c["name"]) for c in columns]
    select_clause = ", ".join(quote_identifier(c) for c in select_cols)
    sql = (
        f"SELECT {select_clause} "
        f"FROM {quote_identifier(owner)}.{quote_identifier(object_name)}"
    )

    binds: dict[str, Any] = {}
    conditions: list[str] = []
    for flt in filters or []:
        col = _whitelist_column(str(flt["column"]), whitelist)
        op = str(flt["operator"]).upper()
        if op not in FILTER_OPERATORS:
            raise ServiceError(
                ErrorCode.SQL_NOT_ALLOWED,
                f"Toán tử filter không hợp lệ: {op!r}.",
            )
        code = str(flt["code"])
        _validate_identifier(code, "mã tham số")
        value = flt.get("value")
        col_expr = quote_identifier(col)
        if op == "IS_NULL":
            conditions.append(f"{col_expr} IS NULL")
            continue
        if value is None or value == "" or value == []:
            continue
        if op in ("=", ">=", "<="):
            conditions.append(f"{col_expr} {op} :{code}")
            binds[code] = value
        elif op == "BETWEEN":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ServiceError(
                    ErrorCode.SQL_NOT_ALLOWED,
                    f"Filter BETWEEN của {code!r} cần đúng 2 giá trị.",
                )
            conditions.append(f"{col_expr} BETWEEN :{code}_from AND :{code}_to")
            binds[f"{code}_from"] = value[0]
            binds[f"{code}_to"] = value[1]
        elif op == "IN":
            if not isinstance(value, (list, tuple)) or len(value) == 0:
                raise ServiceError(
                    ErrorCode.SQL_NOT_ALLOWED,
                    f"Filter IN của {code!r} cần danh sách giá trị không rỗng.",
                )
            placeholders = ", ".join(f":{code}_{i+1}" for i in range(len(value)))
            conditions.append(f"{col_expr} IN ({placeholders})")
            for i, item in enumerate(value):
                binds[f"{code}_{i+1}"] = item
        elif op == "LIKE_PREFIX":
            conditions.append(f"{col_expr} LIKE :{code}")
            binds[code] = f"{value}%"

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    order_parts: list[str] = []
    for srt in sorts or []:
        col = _whitelist_column(str(srt["column"]), whitelist)
        direction = str(srt["direction"]).upper()
        if direction not in ("ASC", "DESC"):
            raise ServiceError(
                ErrorCode.SQL_NOT_ALLOWED,
                f"Hướng sắp xếp không hợp lệ: {direction!r}.",
            )
        order_parts.append(f"{quote_identifier(col)} {direction}")
    if order_parts:
        sql += " ORDER BY " + ", ".join(order_parts)

    return sql, binds


def _ds_timeout_seconds(data_source_id: int) -> int:
    """Đọc CALL_TIMEOUT_S của Data Source; không tồn tại thì NOT_FOUND."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(recon_data_source.c.CALL_TIMEOUT_S).where(
                    recon_data_source.c.ID == data_source_id
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            f"Nguồn dữ liệu ID={data_source_id} không tồn tại",
        )
    return int(row["CALL_TIMEOUT_S"] or 600)


def _effective_timeout_sec(requested_sec: int, ds_timeout_sec: int) -> int:
    """Timeout thực dùng = min(timeout yêu cầu, timeout Data Source) (Q4)."""
    return min(max(int(requested_sec), 1), ds_timeout_sec)


def _assert_read_only(ora_conn: Any) -> None:
    """Chặn account Data Source có quyền ghi (Q5, T22-09).

    USER_SYS_PRIVS luôn đọc được với mọi account nên lỗi truy vấn ở đây
    coi như không có quyền ghi (cùng cách xử lý của data_source).
    """
    cursor = ora_conn.cursor()
    try:
        placeholders = ", ".join(f"'{p}'" for p in _WRITE_PRIVILEGES)
        cursor.execute(
            "SELECT PRIVILEGE FROM USER_SYS_PRIVS "
            f"WHERE PRIVILEGE IN ({placeholders})"
        )
        write_privs = [str(r[0]) for r in cursor.fetchall()]
    except Exception:
        write_privs = []
    finally:
        try:
            cursor.close()
        except Exception:
            pass
    if write_privs:
        raise ServiceError(
            ErrorCode.DS_NOT_READ_ONLY,
            "Tài khoản nguồn dữ liệu có quyền ghi "
            f"({', '.join(write_privs)}); báo cáo yêu cầu tài khoản chỉ đọc.",
        )


@contextmanager
def _open_checked_connection(
    data_source_id: int, timeout_sec: int
) -> Iterator[Any]:
    """Context manager: kết nối Oracle đã kiểm tra read-only, siết timeout (Q4/Q5)."""
    ds_timeout = _ds_timeout_seconds(data_source_id)
    ora_conn = open_source_connection(data_source_id)
    try:
        ora_conn.call_timeout = _effective_timeout_sec(timeout_sec, ds_timeout) * 1000
        _assert_read_only(ora_conn)
        yield ora_conn
    finally:
        ora_conn.close()


def _describe_custom_sql(
    data_source_id: int, sql_text: str, timeout_sec: int
) -> dict[str, Any]:
    """Describe SQL CUSTOM_SQL qua Oracle (0 dòng); trả {"binds", "columns"}.

    Hàm thuần dùng chung cho validate_version_sql và analyze_version_source.
    Lỗi SQL → SQL_NOT_ALLOWED; describe thất bại → SQL_DESCRIBE_FAILED.
    """
    ok, reason, binds = check_report_sql(sql_text)
    if not ok:
        raise ServiceError(
            ErrorCode.SQL_NOT_ALLOWED, reason or "Câu lệnh SQL không hợp lệ."
        )
    with _open_checked_connection(data_source_id, timeout_sec) as conn:
        try:
            columns = describe_sql(conn, sql_text)
        except Exception as exc:
            raise ServiceError(
                ErrorCode.SQL_DESCRIBE_FAILED,
                f"Không thể phân tích câu lệnh SQL: {exc}",
            ) from exc
    return {"binds": binds, "columns": columns}


def _discover_object_columns(
    data_source_id: int, owner: str, object_name: str, timeout_sec: int
) -> list[dict[str, Any]]:
    """Cột của VIEW/TABLE với kiểu đã map sang kiểu báo cáo (hàm thuần)."""
    # Mở kết nối chỉ để kiểm tra read-only (Q5); list_columns tự mở kết
    # nối riêng của nó (có cache 10 phút).
    with _open_checked_connection(data_source_id, timeout_sec):
        pass
    columns = list_columns(data_source_id, owner, object_name)
    return [
        {
            "name": c["name"],
            "data_type": map_oracle_type(str(c["data_type"])),
            "oracle_data_type": str(c["data_type"]),
            "nullable": bool(c["nullable"]),
            "length": c.get("length"),
            "precision": c.get("precision"),
            "scale": c.get("scale"),
        }
        for c in columns
    ]


def _load_version_source(
    conn: Connection, version_id: int
) -> tuple[Any, Sequence[Any], Sequence[Any]]:
    """Đọc version + cột + tham số hiện tại; version không có thì NOT_FOUND."""
    row = (
        conn.execute(
            select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            f"Version báo cáo ID={version_id} không tồn tại",
        )
    columns = (
        conn.execute(
            select(recon_rpt_column).where(
                recon_rpt_column.c.VERSION_ID == version_id
            )
        )
        .mappings()
        .all()
    )
    params = (
        conn.execute(
            select(recon_rpt_param).where(
                recon_rpt_param.c.VERSION_ID == version_id
            )
        )
        .mappings()
        .all()
    )
    return row, columns, params


@service
@requires_menu("report_admin")
def validate_version_sql(
    ctx: Ctx,
    sql_text: str,
    data_source_id: int,
    timeout_sec: int = DEFAULT_DESCRIBE_TIMEOUT_SEC,
) -> dict[str, Any]:
    """Kiểm tra SQL CUSTOM_SQL của version và describe thử (0 dòng).

    Trả về {"binds": [...], "columns": [{"name", "data_type", ...}]}.
    Lỗi SQL → SQL_NOT_ALLOWED; describe thất bại → SQL_DESCRIBE_FAILED.
    """
    return _describe_custom_sql(data_source_id, sql_text, timeout_sec)


@service
@requires_menu("report_admin")
def list_report_objects(
    ctx: Ctx,
    data_source_id: int,
    source_type: str,
    q: str | None = None,
    timeout_sec: int = DEFAULT_DESCRIBE_TIMEOUT_SEC,
) -> list[dict[str, Any]]:
    """Liệt kê VIEW hoặc TABLE của Data Source (T22-04, T22-05).

    Chỉ trả object mà account có quyền SELECT (ALL_VIEWS/ALL_TABLES vốn
    đã giới hạn như vậy). Kiểm tra read-only trước khi discover (Q5).
    """
    if source_type not in ("VIEW", "TABLE"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Loại nguồn phải là VIEW hoặc TABLE.",
        )
    # Mở kết nối chỉ để kiểm tra read-only (Q5); list_tables tự mở kết
    # nối riêng của nó (có cache 10 phút).
    with _open_checked_connection(data_source_id, timeout_sec):
        pass
    return list_tables(data_source_id, q=q, object_type=source_type)


@service
@requires_menu("report_admin")
def list_report_columns(
    ctx: Ctx,
    data_source_id: int,
    owner: str,
    object_name: str,
    timeout_sec: int = DEFAULT_DESCRIBE_TIMEOUT_SEC,
) -> list[dict[str, Any]]:
    """Liệt kê cột của VIEW/TABLE với kiểu đã map sang kiểu báo cáo (T22-07)."""
    if not owner or not owner.strip() or not object_name or not object_name.strip():
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Cần chỉ định schema và tên đối tượng.",
        )
    return _discover_object_columns(data_source_id, owner, object_name, timeout_sec)


@service
@requires_menu("report_admin")
def analyze_version_source(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Describe lại nguồn của version và so với cột/tham số hiện tại (T22-08).

    Chỉ đọc, không ghi. Trả diff {"added": [...], "removed": [...],
    "type_changed": [{"name", "old_type", "new_type"}], "new_binds": [...],
    "missing_binds": [...]}. Với CUSTOM_SQL, binds so theo CODE tham số;
    với VIEW/TABLE, missing_binds là tham số có FILTER_COLUMN đã mất.
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        ver, columns, params = _load_version_source(conn, version_id)
    source_type = ver["SOURCE_TYPE"]
    if not source_type:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Version chưa cấu hình nguồn dữ liệu.",
        )
    ds_id = ver["DATA_SOURCE_ID"]
    if ds_id is None:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Version chưa chọn nguồn dữ liệu.",
        )
    timeout = int(ver["TIMEOUT_SEC"] or DEFAULT_DESCRIBE_TIMEOUT_SEC)
    if source_type == "CUSTOM_SQL":
        described = _describe_custom_sql(ds_id, ver["SQL_TEXT"] or "", timeout)
        discovered = [
            {
                "name": c["name"],
                "data_type": map_oracle_type(str(c["data_type"])),
                "oracle_data_type": str(c["data_type"]),
                "nullable": bool(c.get("nullable", True)),
                "length": c.get("length"),
                "precision": c.get("precision"),
                "scale": c.get("scale"),
            }
            for c in described["columns"]
        ]
        discovered_binds: set[str] | None = set(described["binds"])
    elif source_type in ("VIEW", "TABLE"):
        discovered = _discover_object_columns(
            ds_id, ver["SOURCE_OWNER"], ver["SOURCE_OBJECT"], timeout
        )
        discovered_binds = None
    else:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Loại nguồn không hỗ trợ: {source_type}.",
        )

    current = {str(c["FIELD_NAME"]).upper(): c for c in columns}
    discovered_by_name = {str(d["name"]).upper(): d for d in discovered}
    added = [d for k, d in discovered_by_name.items() if k not in current]
    removed = [str(c["FIELD_NAME"]) for k, c in current.items() if k not in discovered_by_name]
    type_changed = [
        {
            "name": str(current[k]["FIELD_NAME"]),
            "old_type": str(current[k]["DATA_TYPE"]),
            "new_type": str(discovered_by_name[k]["data_type"]),
        }
        for k in current
        if k in discovered_by_name
        and str(current[k]["DATA_TYPE"]).upper()
        != str(discovered_by_name[k]["data_type"]).upper()
    ]
    param_codes = {str(p["CODE"]) for p in params}
    if discovered_binds is not None:
        new_binds = sorted(discovered_binds - param_codes)
        missing_binds = sorted(param_codes - discovered_binds)
    else:
        removed_upper = {r.upper() for r in removed}
        new_binds = []
        missing_binds = sorted(
            str(p["CODE"])
            for p in params
            if p["FILTER_COLUMN"] and str(p["FILTER_COLUMN"]).upper() in removed_upper
        )
    return {
        "added": added,
        "removed": removed,
        "type_changed": type_changed,
        "new_binds": new_binds,
        "missing_binds": missing_binds,
    }


@service
@requires_menu("report_admin")
def apply_source_diff(
    ctx: Ctx, version_id: int, diff: dict[str, Any]
) -> dict[str, Any]:
    """Áp diff nguồn vào version DRAFT trong một transaction (T22-08).

    Cột mới: thêm với WEB/EXCEL_VISIBLE='Y', DISPLAY_ORDER nối tiếp (+10).
    Cột mất: giữ dòng nhưng tắt WEB/EXCEL_VISIBLE (Q6 — để wizard/task 27
    cho xem lại rồi xóa tay). Cột đổi type: cập nhật DATA_TYPE. Tham số
    theo binds mới/mất chỉ báo trong diff, không tự thêm/xóa (task 23).
    Ghi audit UPDATE_VERSION_SOURCE cùng transaction.
    """
    engine = get_recon_engine()
    with engine.begin() as conn:
        ver, columns, _params = _load_version_source(conn, version_id)
        if ver["STATUS"] != "DRAFT":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ áp dụng diff nguồn cho version DRAFT; "
                "version đã khóa cần clone mới (task 21).",
            )
        current = {str(c["FIELD_NAME"]).upper(): c for c in columns}
        max_order = max((int(c["DISPLAY_ORDER"]) for c in columns), default=0)
        n_added = 0
        for col in diff.get("added") or []:
            name = str(col["name"]).upper()
            if name in current:
                continue
            max_order += 10
            conn.execute(
                recon_rpt_column.insert().values(
                    VERSION_ID=version_id,
                    FIELD_NAME=name,
                    LABEL=name,
                    DATA_TYPE=str(col.get("data_type") or "STRING"),
                    DISPLAY_ORDER=max_order,
                    WEB_VISIBLE="Y",
                    EXCEL_VISIBLE="Y",
                    ALIGNMENT="LEFT",
                    IS_TOTAL="N",
                )
            )
            n_added += 1
        n_removed = 0
        for name in diff.get("removed") or []:
            row = current.get(str(name).upper())
            if row is None:
                continue
            conn.execute(
                recon_rpt_column.update()
                .where(recon_rpt_column.c.ID == row["ID"])
                .values(WEB_VISIBLE="N", EXCEL_VISIBLE="N")
            )
            n_removed += 1
        n_changed = 0
        for ch in diff.get("type_changed") or []:
            row = current.get(str(ch["name"]).upper())
            if row is None:
                continue
            conn.execute(
                recon_rpt_column.update()
                .where(recon_rpt_column.c.ID == row["ID"])
                .values(DATA_TYPE=str(ch["new_type"]))
            )
            n_changed += 1
        write_audit_log(
            conn,
            "RECON_RPT_TPL_VER",
            version_id,
            "UPDATE_VERSION_SOURCE",
            ctx.username,
            new_data={
                "added": [str(c["name"]) for c in diff.get("added") or []],
                "removed": list(diff.get("removed") or []),
                "type_changed": list(diff.get("type_changed") or []),
            },
        )
    return {"added": n_added, "removed": n_removed, "type_changed": n_changed}
