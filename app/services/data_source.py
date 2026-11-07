from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import oracledb
from sqlalchemy import Engine, create_engine, func, select, text, update

from app.core.audit import write_audit_log
from app.core.config import get_settings
from app.core.context import Ctx
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source, recon_template_version
from app.schemas.data_source import (
    DataSourceCreateDTO,
    DataSourceOption,
    DataSourceResponse,
    DataSourceUpdateDTO,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import require_admin, requires_menu


def _build_ds_response(row: Any, template_count: int = 0) -> DataSourceResponse:
    """Tạo đối tượng DataSourceResponse từ dòng dữ liệu DB (không chứa mật khẩu)."""
    return DataSourceResponse(
        id=int(row["ID"]),
        name=str(row["NAME"]),
        env=str(row["ENV"]),
        purpose=str(row["PURPOSE"]),
        db_type=str(row["DB_TYPE"]),
        host=row["HOST"],
        port=row["PORT"],
        service_name=row["SERVICE_NAME"],
        file_path=row["FILE_PATH"],
        username=row["USERNAME"],
        default_schema=row["DEFAULT_SCHEMA"],
        call_timeout_s=int(row["CALL_TIMEOUT_S"] or 600),
        max_rows=int(row["MAX_ROWS"] or 1000000),
        is_active=(row["IS_ACTIVE"] == "Y"),
        is_current_metadata=(row["IS_CURRENT_METADATA"] == "Y"),
        last_test_at=row["LAST_TEST_AT"],
        last_test_ok=row["LAST_TEST_OK"],
        last_test_msg=row["LAST_TEST_MSG"],
        last_test_ms=row["LAST_TEST_MS"],
        template_count=template_count,
        created_by=str(row["CREATED_BY"]),
        created_at=row["CREATED_AT"],
        updated_at=row["UPDATED_AT"],
    )


@service
@requires_menu("data_source")
def list_data_sources(
    ctx: Ctx,
    purpose: str | None = None,
) -> list[DataSourceResponse]:
    """Danh sách tất cả Data Source (chỉ dành cho Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)

    with engine.connect() as conn:
        stmt = select(recon_data_source).order_by(recon_data_source.c.ENV, recon_data_source.c.NAME)
        if purpose:
            stmt = stmt.where(recon_data_source.c.PURPOSE == purpose.upper())

        rows = conn.execute(stmt).mappings().all()

        # Đếm số template đang liên kết với từng data source
        tmpl_stmt = (
            select(
                recon_template_version.c.DATA_SOURCE_ID,
                func.count(func.distinct(recon_template_version.c.TEMPLATE_ID)),
            )
            .where(recon_template_version.c.STATUS == "ACTIVE")
            .group_by(recon_template_version.c.DATA_SOURCE_ID)
        )
        tmpl_map: dict[int, int] = {}
        for r_id, count in conn.execute(tmpl_stmt).all():
            if r_id is not None:
                tmpl_map[int(r_id)] = int(count)

        return [_build_ds_response(r, template_count=tmpl_map.get(int(r["ID"]), 0)) for r in rows]


@service
@requires_menu("template", "data_source", "batch_run", any_of=True)
def options_data_sources(
    ctx: Ctx,
    purpose: str | None = None,
) -> list[DataSourceOption]:
    """Danh sách tùy chọn Data Source đang hoạt động (cho mọi vai trò đã đăng nhập)."""

    engine = get_recon_engine()

    with engine.connect() as conn:
        stmt = (
            select(
                recon_data_source.c.ID,
                recon_data_source.c.NAME,
                recon_data_source.c.ENV,
                recon_data_source.c.PURPOSE,
                recon_data_source.c.DB_TYPE,
                recon_data_source.c.DEFAULT_SCHEMA,
            )
            .where(recon_data_source.c.IS_ACTIVE == "Y")
            .order_by(recon_data_source.c.NAME)
        )
        if purpose:
            stmt = stmt.where(recon_data_source.c.PURPOSE == purpose.upper())

        rows = conn.execute(stmt).mappings().all()
        return [
            DataSourceOption(
                id=int(r["ID"]),
                name=str(r["NAME"]),
                env=str(r["ENV"]),
                purpose=str(r["PURPOSE"]),
                db_type=str(r["DB_TYPE"]),
                default_schema=r["DEFAULT_SCHEMA"],
            )
            for r in rows
        ]


@service
@requires_menu("data_source")
def create_data_source(ctx: Ctx, dto: DataSourceCreateDTO) -> DataSourceResponse:
    """Tạo Data Source mới (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    norm_name = dto.name.strip().upper()
    norm_env = dto.env.strip().upper()

    with engine.begin() as conn:
        # Kiểm tra trùng tên theo môi trường
        existing = conn.execute(
            select(recon_data_source.c.ID)
            .where(recon_data_source.c.NAME == norm_name)
            .where(recon_data_source.c.ENV == norm_env)
        ).scalar_one_or_none()

        if existing is not None:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Data Source '{norm_name}' trên môi trường '{norm_env}' đã tồn tại",
            )

        enc_password = encrypt_secret(dto.password) if dto.password else None

        ins_res = conn.execute(
            recon_data_source.insert().values(
                NAME=norm_name,
                ENV=norm_env,
                PURPOSE=dto.purpose.upper(),
                DB_TYPE=dto.db_type.upper(),
                HOST=dto.host.strip() if dto.host else None,
                PORT=dto.port,
                SERVICE_NAME=dto.service_name.strip() if dto.service_name else None,
                FILE_PATH=dto.file_path.strip() if dto.file_path else None,
                USERNAME=dto.username.strip() if dto.username else None,
                PASSWORD_ENC=enc_password,
                DEFAULT_SCHEMA=dto.default_schema.strip() if dto.default_schema else None,
                CALL_TIMEOUT_S=dto.call_timeout_s,
                MAX_ROWS=dto.max_rows,
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        if ins_res.inserted_primary_key is None:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không lấy được ID Data Source vừa tạo")
        ds_id = int(ins_res.inserted_primary_key[0])

        write_audit_log(
            conn=conn,
            entity="DATA_SOURCE",
            entity_id=ds_id,
            action="CREATE_DATA_SOURCE",
            actor=ctx.username,
            new_data={
                "name": norm_name,
                "env": norm_env,
                "purpose": dto.purpose,
                "db_type": dto.db_type,
                "host": dto.host,
                "username": dto.username,
                "password": "***",
            },
            now=now,
        )

        row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().one()
        return _build_ds_response(row)


@service
@requires_menu("data_source")
def update_data_source(
    ctx: Ctx,
    ds_id: int,
    dto: DataSourceUpdateDTO,
) -> DataSourceResponse:
    """Cập nhật cấu hình Data Source (chỉ Admin).

    Nếu password rỗng hoặc None thì giữ nguyên mật khẩu cũ.
    """
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().first()

        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Data Source")

        update_vals: dict[str, Any] = {"UPDATED_AT": now}

        if dto.name is not None:
            update_vals["NAME"] = dto.name.strip().upper()
        if dto.host is not None:
            update_vals["HOST"] = dto.host.strip() if dto.host else None
        if dto.port is not None:
            update_vals["PORT"] = dto.port
        if dto.service_name is not None:
            update_vals["SERVICE_NAME"] = dto.service_name.strip() if dto.service_name else None
        if dto.file_path is not None:
            update_vals["FILE_PATH"] = dto.file_path.strip() if dto.file_path else None
        if dto.username is not None:
            update_vals["USERNAME"] = dto.username.strip() if dto.username else None
        if dto.default_schema is not None:
            update_vals["DEFAULT_SCHEMA"] = dto.default_schema.strip() if dto.default_schema else None
        if dto.call_timeout_s is not None:
            update_vals["CALL_TIMEOUT_S"] = dto.call_timeout_s
        if dto.max_rows is not None:
            update_vals["MAX_ROWS"] = dto.max_rows
        if dto.is_active is not None:
            update_vals["IS_ACTIVE"] = "Y" if dto.is_active else "N"

        # Nếu có truyền password mới không rỗng -> cập nhật
        if dto.password and dto.password.strip():
            update_vals["PASSWORD_ENC"] = encrypt_secret(dto.password.strip())

        conn.execute(update(recon_data_source).where(recon_data_source.c.ID == ds_id).values(**update_vals))

        write_audit_log(
            conn=conn,
            entity="DATA_SOURCE",
            entity_id=ds_id,
            action="UPDATE_DATA_SOURCE",
            actor=ctx.username,
            old_data={k: row[k] for k in update_vals if k != "PASSWORD_ENC"},
            new_data={k: v for k, v in update_vals.items() if k != "PASSWORD_ENC"},
            now=now,
        )

        updated_row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().one()
        return _build_ds_response(updated_row)


@service
@requires_menu("data_source")
def activate_data_source(
    ctx: Ctx,
    ds_id: int,
) -> DataSourceResponse:
    """Kích hoạt Data Source (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().first()

        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Data Source")

        if row["PURPOSE"] == "SOURCE":
            conn.execute(
                update(recon_data_source)
                .where(recon_data_source.c.PURPOSE == "SOURCE")
                .where(recon_data_source.c.ID != ds_id)
                .values(IS_ACTIVE="N", UPDATED_AT=now)
            )

        conn.execute(
            update(recon_data_source).where(recon_data_source.c.ID == ds_id).values(IS_ACTIVE="Y", UPDATED_AT=now)
        )

        write_audit_log(
            conn=conn,
            entity="DATA_SOURCE",
            entity_id=ds_id,
            action="ACTIVATE_DATA_SOURCE",
            actor=ctx.username,
            old_data={"is_active": "N"},
            new_data={"is_active": "Y"},
            now=now,
        )

        updated_row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().one()
        return _build_ds_response(updated_row)


def get_active_environment() -> str:
    """Lấy môi trường nguồn đang active (ví dụ DEV, TEST, UAT, PROD)."""
    try:
        engine = get_recon_engine()
        with engine.connect() as conn:
            row = conn.execute(
                select(recon_data_source.c.ENV)
                .where(recon_data_source.c.IS_ACTIVE == "Y")
                .where(recon_data_source.c.PURPOSE == "SOURCE")
                .order_by(recon_data_source.c.UPDATED_AT.desc())
            ).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return get_settings().APP_ENV


@service
@requires_menu("data_source")
def deactivate_data_source(
    ctx: Ctx,
    ds_id: int,
    force: bool = False,
) -> DataSourceResponse:
    """Vô hiệu hóa Data Source (chỉ Admin).

    Không cho phép vô hiệu hóa Data Source lưu trữ RECON_APP hiện tại.
    """
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().first()

        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Data Source")

        if row["IS_CURRENT_METADATA"] == "Y":
            raise ServiceError(
                ErrorCode.DS_CURRENT_METADATA_LOCKED,
                "Không thể vô hiệu hóa kho lưu trữ metadata RECON_APP đang sử dụng",
            )

        conn.execute(
            update(recon_data_source).where(recon_data_source.c.ID == ds_id).values(IS_ACTIVE="N", UPDATED_AT=now)
        )

        write_audit_log(
            conn=conn,
            entity="DATA_SOURCE",
            entity_id=ds_id,
            action="DEACTIVATE_DATA_SOURCE",
            actor=ctx.username,
            old_data={"is_active": "Y"},
            new_data={"is_active": "N"},
            now=now,
        )

        updated_row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().one()
        return _build_ds_response(updated_row)


def _test_oracle_connection(
    host: str,
    port: int,
    service_name: str,
    username: str,
    password: str,
    call_timeout_s: int = 600,
    purpose: str = "SOURCE",
) -> tuple[bool, str, dict[str, Any], int]:
    """Hàm nội bộ kiểm tra kết nối tới Oracle server qua Thin mode."""
    start = time.perf_counter()
    dsn = f"{host}:{port}/{service_name}"
    extra_details: dict[str, Any] = {}

    ora_conn = oracledb.connect(
        user=username,
        password=password,
        dsn=dsn,
    )
    try:
        ora_conn.call_timeout = call_timeout_s * 1000
        version = str(getattr(ora_conn, "version", "19c"))
        cursor = ora_conn.cursor()

        if purpose.upper() == "SOURCE":
            # Kiểm tra quyền ghi: SOURCE chỉ nên là Read-Only
            try:
                cursor.execute(
                    "SELECT PRIVILEGE FROM USER_SYS_PRIVS "
                    "WHERE PRIVILEGE IN ('CREATE TABLE', 'DROP ANY TABLE', 'ALTER ANY TABLE', 'INSERT ANY TABLE', 'UPDATE ANY TABLE', 'DELETE ANY TABLE')"
                )
                write_privs = [str(r[0]) for r in cursor.fetchall()]
            except Exception:
                write_privs = []

            is_read_only = len(write_privs) == 0
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            extra_details["read_only"] = is_read_only
            extra_details["write_privileges"] = write_privs
            extra_details["version"] = version
            extra_details["latency_ms"] = elapsed_ms

            if is_read_only:
                msg = f"Kết nối Oracle {version} thành công ({elapsed_ms}ms). Tài khoản chỉ đọc hợp lệ"
                status = "RO_OK"
            else:
                msg = (
                    f"Kết nối Oracle {version} thành công ({elapsed_ms}ms). "
                    f"Cảnh báo: Tài khoản có quyền ghi ({', '.join(write_privs)})"
                )
                status = "RO_WARN"
            extra_details["status"] = status
            return True, msg, extra_details, elapsed_ms

        elif purpose.upper() == "METADATA":
            cursor.execute("SELECT count(*) FROM USER_TABLES WHERE TABLE_NAME LIKE 'RECON_%'")
            recon_count = int(cursor.fetchone()[0])
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            extra_details["recon_tables_count"] = recon_count
            extra_details["version"] = version
            extra_details["latency_ms"] = elapsed_ms
            extra_details["status"] = "OK"

            if recon_count == 0:
                msg = f"Kết nối Oracle {version} thành công ({elapsed_ms}ms). Schema trống, sẵn sàng tiếp nhận metadata"
            else:
                msg = f"Kết nối Oracle {version} thành công ({elapsed_ms}ms). Schema đã có {recon_count} bảng RECON_*"
            return True, msg, extra_details, elapsed_ms

        else:
            raise ValueError(f"Mục đích '{purpose}' không hợp lệ")
    finally:
        try:
            ora_conn.close()
        except Exception:
            pass


@service
@requires_menu("data_source")
def test_data_source(ctx: Ctx, ds_id: int) -> dict[str, Any]:
    """Kiểm tra kết nối Data Source theo mục đích (SOURCE hoặc METADATA)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.connect() as conn:
        row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().first()

    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Data Source")

    db_type = str(row["DB_TYPE"]).upper()
    purpose = str(row["PURPOSE"]).upper()
    start = time.perf_counter()

    is_ok = False
    msg = ""
    extra_details: dict[str, Any] = {}
    ms = 0

    if db_type == "SQLITE":
        try:
            file_path = row["FILE_PATH"]
            if not file_path:
                raise ValueError("Đường dẫn file SQLite không được để trống")

            p = Path(file_path)
            size_mb = (p.stat().st_size / (1024 * 1024)) if p.exists() else 0.0

            sq_engine = create_engine(f"sqlite:///{p.as_posix()}")
            with sq_engine.connect() as sq_conn:
                sq_conn.execute(text("SELECT 1"))

            is_ok = True
            ms = int((time.perf_counter() - start) * 1000)
            msg = f"Kết nối SQLite thành công. Kích thước file: {size_mb:.2f} MB"
            extra_details["size_mb"] = size_mb
            extra_details["status"] = "OK"
            extra_details["latency_ms"] = ms
        except Exception as exc:
            is_ok = False
            ms = int((time.perf_counter() - start) * 1000)
            msg = f"Kết nối thất bại: {exc}"
            extra_details["status"] = "FAILED"
            extra_details["latency_ms"] = ms

    elif db_type == "ORACLE":
        host = row["HOST"] or ""
        port = int(row["PORT"] or 1521)
        service_name = row["SERVICE_NAME"] or ""
        username = row["USERNAME"] or ""
        plain_password = decrypt_secret(row["PASSWORD_ENC"]) if row["PASSWORD_ENC"] else ""
        call_timeout = int(row["CALL_TIMEOUT_S"] or 600)

        try:
            is_ok, msg, extra_details, ms = _test_oracle_connection(
                host=host,
                port=port,
                service_name=service_name,
                username=username,
                password=plain_password,
                call_timeout_s=call_timeout,
                purpose=purpose,
            )
        except Exception as exc:
            is_ok = False
            ms = int((time.perf_counter() - start) * 1000)
            msg = f"Kết nối thất bại: {exc}"
            extra_details["status"] = "FAILED"
            extra_details["latency_ms"] = ms
    else:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Loại cơ sở dữ liệu '{db_type}' chưa được hỗ trợ")

    # Cập nhật kết quả test vào DB
    test_ok_flag = "W" if (is_ok and extra_details.get("status") == "RO_WARN") else ("Y" if is_ok else "N")
    with engine.begin() as conn:
        conn.execute(
            update(recon_data_source)
            .where(recon_data_source.c.ID == ds_id)
            .values(
                LAST_TEST_AT=now,
                LAST_TEST_OK=test_ok_flag,
                LAST_TEST_MSG=msg[:400],
                LAST_TEST_MS=ms,
            )
        )

    return {
        "ok": is_ok,
        "status": extra_details.get("status", "OK" if is_ok else "FAILED"),
        "message": msg,
        "ms": ms,
        "latency_ms": ms,
        **extra_details,
    }


@service
@requires_menu("data_source")
def test_data_source_config(
    ctx: Ctx,
    host: str,
    port: int,
    service_name: str,
    username: str,
    password: str | None = None,
    ds_id: int | None = None,
    call_timeout_s: int = 600,
    purpose: str = "SOURCE",
) -> dict[str, Any]:
    """Kiểm tra kết nối trực tiếp với các thông số cấu hình."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    plain_password = password
    if (not plain_password or not plain_password.strip()) and ds_id is not None:
        with engine.connect() as conn:
            row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().first()
            if row and row["PASSWORD_ENC"]:
                plain_password = decrypt_secret(row["PASSWORD_ENC"])

    if not plain_password:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Mật khẩu không được để trống khi kiểm tra kết nối")

    try:
        is_ok, msg, extra_details, ms = _test_oracle_connection(
            host=host.strip(),
            port=port,
            service_name=service_name.strip(),
            username=username.strip(),
            password=plain_password,
            call_timeout_s=call_timeout_s,
            purpose=purpose,
        )
    except Exception as exc:
        is_ok = False
        ms = 0
        msg = f"Kết nối thất bại: {exc}"
        extra_details = {"status": "FAILED", "latency_ms": 0}

    # Nếu đang sửa một Data Source đã có ID, cập nhật luôn kết quả test vào DB
    if ds_id is not None:
        test_ok_flag = "W" if (is_ok and extra_details.get("status") == "RO_WARN") else ("Y" if is_ok else "N")
        with engine.begin() as conn:
            conn.execute(
                update(recon_data_source)
                .where(recon_data_source.c.ID == ds_id)
                .values(
                    LAST_TEST_AT=now,
                    LAST_TEST_OK=test_ok_flag,
                    LAST_TEST_MSG=msg[:400],
                    LAST_TEST_MS=ms,
                )
            )

    return {
        "ok": is_ok,
        "status": extra_details.get("status", "OK" if is_ok else "FAILED"),
        "message": msg,
        "ms": ms,
        "latency_ms": ms,
        **extra_details,
    }


def sync_current_metadata_source(engine: Engine | None = None) -> None:
    """Tự động đồng bộ nguồn lưu trữ METADATA hiện tại vào RECON_DATA_SOURCE."""
    if engine is None:
        engine = get_recon_engine()
    settings = get_settings()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    env = settings.APP_ENV.upper()

    db_type = "SQLITE"
    file_path: str | None = None
    host: str | None = None
    port: int | None = None
    service_name: str | None = None
    username: str | None = None

    url = engine.url
    backend = url.get_backend_name().lower()
    if "oracle" in backend:
        db_type = "ORACLE"
        host = url.host
        port = url.port or 1521
        service_name = url.database
        username = url.username
    else:
        db_type = "SQLITE"
        if url.database:
            file_path = str(Path(url.database))
        elif settings.RECON_DB_URL.startswith("sqlite:///"):
            file_path = str(Path(settings.RECON_DB_URL[len("sqlite:///") :]))

    with engine.begin() as conn:
        existing = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.IS_CURRENT_METADATA == "Y"))
            .mappings()
            .first()
        )

        if existing is not None:
            conn.execute(
                update(recon_data_source)
                .where(recon_data_source.c.ID == existing["ID"])
                .values(
                    DB_TYPE=db_type,
                    FILE_PATH=file_path,
                    HOST=host,
                    PORT=port,
                    SERVICE_NAME=service_name,
                    USERNAME=username,
                    ENV=env,
                    UPDATED_AT=now,
                )
            )
        else:
            name = "RECON_APP (Hiện tại)"
            name_exists = conn.execute(
                select(recon_data_source.c.ID)
                .where(recon_data_source.c.NAME == name)
                .where(recon_data_source.c.ENV == env)
            ).scalar_one_or_none()

            if name_exists is not None:
                conn.execute(
                    update(recon_data_source)
                    .where(recon_data_source.c.ID == name_exists)
                    .values(
                        PURPOSE="METADATA",
                        DB_TYPE=db_type,
                        FILE_PATH=file_path,
                        HOST=host,
                        PORT=port,
                        SERVICE_NAME=service_name,
                        USERNAME=username,
                        IS_ACTIVE="Y",
                        IS_CURRENT_METADATA="Y",
                        UPDATED_AT=now,
                    )
                )
            else:
                conn.execute(
                    recon_data_source.insert().values(
                        NAME=name,
                        ENV=env,
                        PURPOSE="METADATA",
                        DB_TYPE=db_type,
                        FILE_PATH=file_path,
                        HOST=host,
                        PORT=port,
                        SERVICE_NAME=service_name,
                        USERNAME=username,
                        PASSWORD_ENC=None,
                        CALL_TIMEOUT_S=600,
                        MAX_ROWS=1000000,
                        IS_ACTIVE="Y",
                        IS_CURRENT_METADATA="Y",
                        CREATED_BY="SYSTEM",
                        CREATED_AT=now,
                        UPDATED_AT=now,
                    )
                )
