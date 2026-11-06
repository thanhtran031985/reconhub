"""Nguồn dữ liệu báo cáo — task 22.

Validator CUSTOM_SQL, discovery metadata Oracle (VIEW/TABLE), query builder
whitelist và diff cột/tham số khi nguồn đổi. Chỉ ADMIN (menu report_admin)
được cấu hình nguồn; chạy báo cáo (task 25) dùng hàm thuần riêng.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source
from app.engine.catalog import describe_sql
from app.engine.sql_guard import check_report_sql
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import requires_menu
from app.services.source_conn import open_source_connection

DEFAULT_DESCRIBE_TIMEOUT_SEC = 300


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
    ds_timeout = _ds_timeout_seconds(data_source_id)
    effective_timeout = _effective_timeout_sec(timeout_sec, ds_timeout)
    ora_conn = open_source_connection(data_source_id)
    try:
        ora_conn.call_timeout = effective_timeout * 1000
        try:
            columns = describe_sql(ora_conn, sql_text)
        except Exception as exc:
            raise ServiceError(
                ErrorCode.SQL_DESCRIBE_FAILED,
                f"Không thể phân tích câu lệnh SQL: {exc}",
            ) from exc
    finally:
        ora_conn.close()
    return {"binds": binds, "columns": columns}
