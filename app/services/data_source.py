from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from app.core.audit import write_audit_log
from app.core.context import Ctx, Role, require_role
from app.core.crypto import encrypt_secret
from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source
from app.schemas.data_source import (
    DataSourceCreateDTO,
    DataSourceOption,
    DataSourceResponse,
    DataSourceUpdateDTO,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service


def _build_ds_response(row: Any) -> DataSourceResponse:
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
        created_by=str(row["CREATED_BY"]),
        created_at=row["CREATED_AT"],
        updated_at=row["UPDATED_AT"],
    )


@service
def list_data_sources(
    ctx: Ctx,
    purpose: str | None = None,
) -> list[DataSourceResponse]:
    """Danh sách tất cả Data Source (chỉ dành cho Admin)."""
    require_role(ctx, Role.ADMIN)
    engine = get_recon_engine()

    with engine.connect() as conn:
        stmt = select(recon_data_source).order_by(recon_data_source.c.ENV, recon_data_source.c.NAME)
        if purpose:
            stmt = stmt.where(recon_data_source.c.PURPOSE == purpose.upper())

        rows = conn.execute(stmt).mappings().all()
        return [_build_ds_response(r) for r in rows]


@service
def options_data_sources(
    ctx: Ctx,
    purpose: str | None = None,
) -> list[DataSourceOption]:
    """Danh sách tùy chọn Data Source đang hoạt động (cho mọi vai trò đã đăng nhập)."""
    require_role(ctx)
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
def create_data_source(ctx: Ctx, dto: DataSourceCreateDTO) -> DataSourceResponse:
    """Tạo Data Source mới (chỉ Admin)."""
    require_role(ctx, Role.ADMIN)
    engine = get_recon_engine()
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
def update_data_source(
    ctx: Ctx,
    ds_id: int,
    dto: DataSourceUpdateDTO,
) -> DataSourceResponse:
    """Cập nhật cấu hình Data Source (chỉ Admin).

    Nếu password rỗng hoặc None thì giữ nguyên mật khẩu cũ.
    """
    require_role(ctx, Role.ADMIN)
    engine = get_recon_engine()
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
def deactivate_data_source(
    ctx: Ctx,
    ds_id: int,
    force: bool = False,
) -> DataSourceResponse:
    """Vô hiệu hóa Data Source (chỉ Admin).

    Không cho phép vô hiệu hóa Data Source lưu trữ RECON_APP hiện tại.
    """
    require_role(ctx, Role.ADMIN)
    engine = get_recon_engine()
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
