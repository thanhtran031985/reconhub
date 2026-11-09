from __future__ import annotations

import oracledb
from sqlalchemy import select

from app.core.crypto import decrypt_secret
from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source
from app.schemas.errors import ErrorCode, ServiceError


def open_source_connection(ds_id: int) -> oracledb.Connection:
    """Mở kết nối tới nguồn Oracle ở chế độ Thin mode có áp dụng call_timeout.

    Ném ServiceError SOURCE_CONNECTION_LOST nếu kết nối thất bại hoặc bị ngắt.
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().first()

    if row is None or row["IS_ACTIVE"] != "Y":
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            f"Nguồn dữ liệu ID={ds_id} không tồn tại hoặc đã bị vô hiệu hóa",
        )

    if str(row["DB_TYPE"]).upper() != "ORACLE":
        raise ServiceError(
            ErrorCode.DS_CONNECT_FAILED,
            f"Chỉ hỗ trợ mở kết nối nguồn cho loại cơ sở dữ liệu ORACLE (hiện tại: {row['DB_TYPE']})",
        )

    host = row["HOST"]
    port = int(row["PORT"] or 1521)
    service_name = row["SERVICE_NAME"]
    username = row["USERNAME"]
    plain_password = decrypt_secret(row["PASSWORD_ENC"]) if row["PASSWORD_ENC"] else ""
    call_timeout_s = int(row["CALL_TIMEOUT_S"] or 600)

    dsn = f"{host}:{port}/{service_name}"

    try:
        ora_conn = oracledb.connect(
            user=username,
            password=plain_password,
            dsn=dsn,
        )
        ora_conn.call_timeout = call_timeout_s * 1000
        # Thiết lập NLS_DATE_FORMAT và NLS_TIMESTAMP_FORMAT chuẩn ISO để tránh ORA-01861
        try:
            cur = ora_conn.cursor()
            cur.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")
            cur.execute("ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS.FF'")
            cur.close()
        except Exception:
            pass
        return ora_conn
    except Exception as exc:
        raise ServiceError(
            ErrorCode.SOURCE_CONNECTION_LOST,
            f"Không thể kết nối đến nguồn dữ liệu Oracle ({host}:{port}/{service_name}): {exc}",
        ) from exc
