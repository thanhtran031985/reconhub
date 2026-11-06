"""Nguồn dữ liệu báo cáo — task 22.

Validator CUSTOM_SQL, discovery metadata Oracle (VIEW/TABLE), query builder
whitelist và diff cột/tham số khi nguồn đổi. Chỉ ADMIN (menu report_admin)
được cấu hình nguồn; chạy báo cáo (task 25) dùng hàm thuần riêng.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import select

from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source
from app.engine.catalog import describe_sql, list_columns, list_tables
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


def _assert_read_only(ora_conn) -> None:
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
def _open_checked_connection(data_source_id: int, timeout_sec: int):
    """Context manager: kết nối Oracle đã kiểm tra read-only, siết timeout (Q4/Q5)."""
    ds_timeout = _ds_timeout_seconds(data_source_id)
    ora_conn = open_source_connection(data_source_id)
    try:
        ora_conn.call_timeout = _effective_timeout_sec(timeout_sec, ds_timeout) * 1000
        _assert_read_only(ora_conn)
        yield ora_conn
    finally:
        ora_conn.close()


@service
@requires_menu("report_admin")
def validate_version_sql(
    ctx: Ctx,
    sql_text: str,
    data_source_id: int,
    timeout_sec: int = DEFAULT_DESCRIBE_TIMEOUT_SEC,
) -> dict:
    """Kiểm tra SQL CUSTOM_SQL của version và describe thử (0 dòng).

    Trả về {"binds": [...], "columns": [{"name", "data_type", ...}]}.
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


@service
@requires_menu("report_admin")
def list_report_objects(
    ctx: Ctx,
    data_source_id: int,
    source_type: str,
    q: str | None = None,
    timeout_sec: int = DEFAULT_DESCRIBE_TIMEOUT_SEC,
) -> list[dict]:
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
) -> list[dict]:
    """Liệt kê cột của VIEW/TABLE với kiểu đã map sang kiểu báo cáo (T22-07)."""
    if not owner or not owner.strip() or not object_name or not object_name.strip():
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Cần chỉ định schema và tên đối tượng.",
        )
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
