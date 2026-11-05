from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, func, select, text, update

from app.core.audit import write_audit_log
from app.core.config import get_settings
from app.core.context import Ctx, Role, require_role
from app.core.crypto import decrypt_secret
from app.db.engine import get_recon_engine
from app.db.metadata import (
    metadata,
    recon_app_setting,
    recon_data_source,
    recon_metadata_migration,
    recon_purge_log,
    recon_run,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service

RECON_TABLES_ORDER = [
    "RECON_USER",
    "RECON_USER_ROLE",
    "RECON_DATA_SOURCE",
    "RECON_TEMPLATE",
    "RECON_TEMPLATE_VERSION",
    "RECON_FILE",
    "RECON_EXCEL_LOAD",
    "RECON_EXCEL_ROW",
    "RECON_RUN",
    "RECON_RUN_QUEUE",
    "RECON_RUN_SUMMARY",
    "RECON_RESULT_ROW",
    "RECON_RESULT_DIFF",
    "RECON_INVALID_ROW",
    "RECON_ISSUE_REASON",
    "RECON_ISSUE",
    "RECON_APP_SETTING",
    "RECON_PURGE_LOG",
    "RECON_LOGIN_LOG",
    "RECON_AUDIT_LOG",
    "RECON_METADATA_MIGRATION",
]

CONFIG_ONLY_TABLES = [
    "RECON_USER",
    "RECON_USER_ROLE",
    "RECON_DATA_SOURCE",
    "RECON_TEMPLATE",
    "RECON_TEMPLATE_VERSION",
    "RECON_APP_SETTING",
    "RECON_ISSUE_REASON",
]


def create_engine_for_ds(row: Any) -> Engine:
    """Tạo SQLAlchemy engine từ thông tin cấu hình Data Source."""
    db_type = str(row["DB_TYPE"]).upper()
    if db_type == "SQLITE":
        file_path = row["FILE_PATH"]
        if not file_path:
            raise ValueError("Đường dẫn file SQLite không được để trống")
        return create_engine(f"sqlite:///{Path(file_path).as_posix()}")
    elif db_type == "ORACLE":
        host = row["HOST"]
        port = int(row["PORT"] or 1521)
        service_name = row["SERVICE_NAME"]
        username = row["USERNAME"]
        plain_password = decrypt_secret(row["PASSWORD_ENC"]) if row["PASSWORD_ENC"] else ""
        return create_engine(
            f"oracle+oracledb://{username}:{plain_password}@{host}:{port}/?service_name={service_name}"
        )
    else:
        raise ValueError(f"Loại cơ sở dữ liệu '{db_type}' chưa được hỗ trợ")


@service
def set_maintenance_mode(ctx: Ctx, enabled: bool) -> dict[str, Any]:
    """Bật/tắt chế độ bảo trì toàn hệ thống."""
    require_role(ctx, Role.ADMIN)
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    val = "Y" if enabled else "N"

    with engine.begin() as conn:
        exists = conn.execute(select(recon_app_setting.c.KEY).where(recon_app_setting.c.KEY == "MAINTENANCE")).scalar()
        if exists:
            conn.execute(
                update(recon_app_setting)
                .where(recon_app_setting.c.KEY == "MAINTENANCE")
                .values(VALUE=val, UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
        else:
            conn.execute(
                recon_app_setting.insert().values(
                    KEY="MAINTENANCE",
                    VALUE=val,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                )
            )

        write_audit_log(
            conn=conn,
            entity="SETTING",
            entity_id="MAINTENANCE",
            action="UPDATE_SETTING",
            actor=ctx.username,
            new_data={"maintenance": val},
            now=now,
        )

    return {"maintenance": val}


@service
def precheck(
    ctx: Ctx,
    target_ds_id: int,
    mode: str = "NO_TEMP",
    mock_target_engine: Engine | None = None,
) -> dict[str, Any]:
    """Kiểm tra điều kiện trước khi chuyển metadata RECON_APP từ SQLite sang Oracle."""
    require_role(ctx, Role.ADMIN)

    if mode not in ("NO_TEMP", "FULL", "CONFIG_ONLY"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Chế độ chuyển '{mode}' không hợp lệ. Phải là một trong: NO_TEMP, FULL, CONFIG_ONLY.",
        )

    src_engine = get_recon_engine()

    # 1. Kiểm tra Data Source đích
    with src_engine.connect() as conn:
        ds_row = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.ID == target_ds_id)).mappings().first()
        )

    if ds_row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy Data Source đích ID {target_ds_id}.")

    if ds_row.get("IS_CURRENT_METADATA") == "Y":
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Không thể chuyển sang chính cơ sở dữ liệu metadata đang dùng.",
        )

    # 2. Kiểm tra không có run nào đang chạy hoặc trong hàng đợi
    with src_engine.connect() as conn:
        busy_runs = conn.execute(
            select(recon_run.c.ID).where(recon_run.c.STATUS.in_(["QUEUED", "PROCESSING", "RUNNING"]))
        ).fetchall()
        if busy_runs:
            busy_ids = [r[0] for r in busy_runs]
            raise ServiceError(
                ErrorCode.MIGRATION_RUNNING,
                f"Không thể chuyển dữ liệu khi có run đang chờ hoặc đang chạy: {busy_ids}.",
            )

    # 3. Kiểm tra kết nối và tính sẵn sàng của đích
    target_engine = mock_target_engine or create_engine_for_ds(ds_row)

    with target_engine.connect() as tgt_conn:
        # Kiểm tra nếu đích đã có bảng RECON_* và có dữ liệu
        for t_name in RECON_TABLES_ORDER:
            try:
                cnt = tgt_conn.execute(text(f"SELECT COUNT(*) FROM {t_name}")).scalar()
                if cnt and cnt > 0:
                    raise ServiceError(
                        ErrorCode.MIGRATION_TARGET_NOT_EMPTY,
                        f"Schema đích không trống: bảng {t_name} đang có {cnt} bản ghi. Hãy xóa bảng RECON_* ở đích trước khi chuyển.",
                    )
            except ServiceError:
                raise
            except Exception:
                # Bảng chưa tồn tại ở đích là hợp lệ
                pass

    # 4. Ước tính số dòng và dung lượng các bảng cần chép
    tables_to_copy = RECON_TABLES_ORDER
    if mode == "CONFIG_ONLY":
        tables_to_copy = CONFIG_ONLY_TABLES
    elif mode == "NO_TEMP":
        tables_to_copy = [t for t in RECON_TABLES_ORDER if t not in ("RECON_EXCEL_LOAD", "RECON_EXCEL_ROW")]

    table_estimates: list[dict[str, Any]] = []
    total_rows = 0

    with src_engine.connect() as src_conn:
        for t_name in tables_to_copy:
            if t_name in metadata.tables:
                tbl = metadata.tables[t_name]
                r_cnt = src_conn.execute(select(func.count()).select_from(tbl)).scalar() or 0
                est_bytes = r_cnt * 200
                total_rows += r_cnt
                table_estimates.append({"table": t_name, "rows": r_cnt, "bytes_est": est_bytes})

    total_est_bytes = total_rows * 200

    return {
        "target_ds_id": target_ds_id,
        "target_name": ds_row["NAME"],
        "target_env": ds_row["ENV"],
        "mode": mode,
        "can_migrate": True,
        "ready": True,
        "tables": table_estimates,
        "total_rows": total_rows,
        "total_bytes_est": total_est_bytes,
    }


def _calculate_table_checksum(conn: Any, table: Any) -> str:
    """Tính checksum SHA256 của các khóa chính trong bảng."""
    pk_cols = [c for c in table.primary_key.columns]
    if not pk_cols:
        return ""
    pk_col = pk_cols[0]
    rows = conn.execute(select(pk_col).order_by(pk_col)).fetchall()
    joined_ids = ",".join(str(r[0]) for r in rows)
    return hashlib.sha256(joined_ids.encode("utf-8")).hexdigest()


def _copy_table_data(tgt_conn: Any, tbl: Any, chunk: list[dict[str, Any]]) -> None:
    """Sao chép lô dữ liệu sang bảng đích."""
    if chunk:
        tgt_conn.execute(tbl.insert(), chunk)


@service
def start_migration(
    ctx: Ctx,
    target_ds_id: int,
    mode: str = "NO_TEMP",
    mock_target_engine: Engine | None = None,
) -> dict[str, Any]:
    """Thực thi chuyển toàn bộ metadata sang Oracle đích với đối chiếu và đồng bộ identity."""
    require_role(ctx, Role.ADMIN)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    src_engine = get_recon_engine()

    # Bước 1: Precheck
    precheck(ctx, target_ds_id, mode=mode, mock_target_engine=mock_target_engine)

    with src_engine.connect() as conn:
        ds_row = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.ID == target_ds_id)).mappings().first()
        )
    assert ds_row is not None

    target_engine = mock_target_engine or create_engine_for_ds(ds_row)

    # Bước 2: Bật chế độ bảo trì
    set_maintenance_mode(ctx, enabled=True)

    # Ghi nhận RECON_METADATA_MIGRATION
    with src_engine.begin() as conn:
        ins = conn.execute(
            recon_metadata_migration.insert().values(
                SOURCE_DS_ID=1,
                TARGET_DS_ID=target_ds_id,
                STATUS="PROCESSING",
                MODE=mode,
                STAGE="CREATE_SCHEMA",
                PROGRESS_PCT=10,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
            )
        )
        migration_id = int(ins.inserted_primary_key[0]) if ins.inserted_primary_key else 1

    tables_to_copy = RECON_TABLES_ORDER
    if mode == "CONFIG_ONLY":
        tables_to_copy = CONFIG_ONLY_TABLES
    elif mode == "NO_TEMP":
        tables_to_copy = [t for t in RECON_TABLES_ORDER if t not in ("RECON_EXCEL_LOAD", "RECON_EXCEL_ROW")]

    report_rows: dict[str, Any] = {}
    total_tables = len(tables_to_copy)

    try:
        # Bước 3: Tạo bảng trên đích
        metadata.create_all(target_engine)

        with src_engine.connect() as src_conn, target_engine.begin() as tgt_conn:
            for idx, t_name in enumerate(tables_to_copy, 1):
                tbl = metadata.tables[t_name]

                # Đọc từ nguồn theo khóa chính
                pk_cols = [c for c in tbl.primary_key.columns]
                order_expr = pk_cols[0].asc() if pk_cols else None
                sel_stmt = select(tbl)
                if order_expr is not None:
                    sel_stmt = sel_stmt.order_by(order_expr)

                src_records = src_conn.execute(sel_stmt).mappings().fetchall()
                record_dicts = [dict(r) for r in src_records]

                # Nếu ở chế độ NO_TEMP đối với RECON_RUN, gắn cờ TEMP_PURGED_AT nếu chưa có
                if mode == "NO_TEMP" and t_name == "RECON_RUN":
                    for r_dict in record_dicts:
                        if not r_dict.get("TEMP_PURGED_AT"):
                            r_dict["TEMP_PURGED_AT"] = now
                            r_dict["TEMP_PURGED_BY"] = ctx.username

                # Ghi sang đích theo lô 5.000 dòng
                batch_size = 5000
                for i in range(0, len(record_dicts), batch_size):
                    chunk = record_dicts[i : i + batch_size]
                    if chunk:
                        _copy_table_data(tgt_conn, tbl, chunk)

                # Cập nhật tiến độ
                pct = int(10 + (idx / total_tables) * 70)
                with src_engine.begin() as upd_conn:
                    upd_conn.execute(
                        update(recon_metadata_migration)
                        .where(recon_metadata_migration.c.ID == migration_id)
                        .values(STAGE=f"COPY_{t_name}", PROGRESS_PCT=pct)
                    )

                # Đồng bộ Identity cho Oracle
                if target_engine.dialect.name == "oracle" and "ID" in tbl.c:
                    max_id = tgt_conn.execute(select(func.coalesce(func.max(tbl.c.ID), 0))).scalar() or 0
                    next_id = int(max_id) + 1
                    try:
                        tgt_conn.execute(
                            text(f"ALTER TABLE {t_name} MODIFY ID GENERATED AS IDENTITY (START WITH {next_id})")
                        )
                    except Exception:
                        pass

                # Đối chiếu số dòng
                tgt_cnt = tgt_conn.execute(select(func.count()).select_from(tbl)).scalar() or 0
                if tgt_cnt != len(record_dicts):
                    raise ServiceError(
                        ErrorCode.MIGRATION_COUNT_MISMATCH,
                        f"Số dòng bảng {t_name} không khớp: nguồn {len(record_dicts)}, đích {tgt_cnt}.",
                    )

                report_rows[t_name] = {
                    "source_rows": len(record_dicts),
                    "target_rows": tgt_cnt,
                    "matched": True,
                }

        # Bước 4: Checksum trên 3 bảng lớn nhất
        with src_engine.connect() as src_conn, target_engine.connect() as tgt_conn:
            sorted_tables = sorted(report_rows.items(), key=lambda item: item[1]["source_rows"], reverse=True)[:3]
            for t_name, _ in sorted_tables:
                tbl = metadata.tables[t_name]
                cs_src = _calculate_table_checksum(src_conn, tbl)
                cs_tgt = _calculate_table_checksum(tgt_conn, tbl)
                if cs_src != cs_tgt:
                    raise ServiceError(
                        ErrorCode.MIGRATION_COUNT_MISMATCH,
                        f"Checksum SHA256 bảng {t_name} không khớp giữa nguồn và đích.",
                    )
                report_rows[t_name]["checksum_matched"] = True

        # Hoàn tất thành công
        fin_now = datetime.now(timezone.utc).replace(tzinfo=None)
        settings = get_settings()
        old_sqlite_file = settings.RECON_DB_URL.replace("sqlite:///", "")

        with src_engine.begin() as conn:
            conn.execute(
                update(recon_metadata_migration)
                .where(recon_metadata_migration.c.ID == migration_id)
                .values(
                    STATUS="DONE",
                    STAGE="COMPLETED",
                    PROGRESS_PCT=100,
                    REPORT_JSON=report_rows,
                    OLD_SQLITE_PATH=old_sqlite_file,
                    FINISHED_AT=fin_now,
                )
            )

        new_dsn = f"oracle+oracledb://{ds_row['USERNAME']}:***@{ds_row['HOST']}:{ds_row['PORT']}/?service_name={ds_row['SERVICE_NAME']}"

        return {
            "migration_id": migration_id,
            "status": "DONE",
            "report": report_rows,
            "old_sqlite_path": old_sqlite_file,
            "next_steps": [
                "1. Dừng ứng dụng web ReconHub và background worker.",
                f"2. Cập nhật biến môi trường RECON_DB_URL trong file .env: {new_dsn}",
                "3. Chạy lệnh kiểm tra schema: uv run poe db-migrate",
                "4. Khởi động lại dịch vụ web và worker để chạy hoàn toàn trên Oracle.",
            ],
        }

    except Exception as exc:
        # Nếu gặp lỗi, SQLite nguồn giữ nguyên, ghi FAILED
        with src_engine.begin() as conn:
            conn.execute(
                update(recon_metadata_migration)
                .where(recon_metadata_migration.c.ID == migration_id)
                .values(
                    STATUS="FAILED",
                    STAGE="ERROR",
                    ERROR_MSG=str(exc),
                    FINISHED_AT=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
        raise


@service
def clean_target_schema(
    ctx: Ctx,
    target_ds_id: int,
    confirm_schema: str,
    mock_target_engine: Engine | None = None,
) -> dict[str, Any]:
    """Xóa toàn bộ bảng RECON_* ở schema đích khi cần thử lại sau khi chuyển lỗi."""
    require_role(ctx, Role.ADMIN)
    src_engine = get_recon_engine()

    with src_engine.connect() as conn:
        ds_row = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.ID == target_ds_id)).mappings().first()
        )

    if ds_row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Data Source đích.")

    expected_schema = str(ds_row["DEFAULT_SCHEMA"] or ds_row["USERNAME"]).upper()
    if confirm_schema.strip().upper() != expected_schema:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Tên schema xác nhận '{confirm_schema}' không khớp với schema đích '{expected_schema}'.",
        )

    target_engine = mock_target_engine or create_engine_for_ds(ds_row)

    # Drop bảng theo thứ tự ngược
    dropped = []
    is_oracle = target_engine.dialect.name == "oracle"
    with target_engine.begin() as conn:
        for t_name in reversed(RECON_TABLES_ORDER):
            try:
                if is_oracle:
                    conn.execute(text(f"DROP TABLE {t_name} CASCADE CONSTRAINTS"))
                else:
                    conn.execute(text(f"DROP TABLE IF EXISTS {t_name}"))
                dropped.append(t_name)
            except Exception:
                pass

    return {"cleaned": True, "dropped_tables": dropped}


@service
def get_migration_status(ctx: Ctx, migration_id: int) -> dict[str, Any]:
    """Lấy trạng thái và báo cáo của phiên di chuyển."""
    require_role(ctx, Role.ADMIN)
    engine = get_recon_engine()
    with engine.connect() as conn:
        row = (
            conn.execute(select(recon_metadata_migration).where(recon_metadata_migration.c.ID == migration_id))
            .mappings()
            .first()
        )
    if not row:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy phiên chuyển dữ liệu.")
    return dict(row)


@service
def list_migrations(ctx: Ctx) -> list[dict[str, Any]]:
    """Danh sách các phiên di chuyển metadata."""
    require_role(ctx, Role.ADMIN)
    engine = get_recon_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(select(recon_metadata_migration).order_by(recon_metadata_migration.c.ID.desc()))
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


@service
def delete_old_sqlite(
    ctx: Ctx,
    confirm_filename: str,
    target_sqlite_path: str | None = None,
) -> dict[str, Any]:
    """Xóa file SQLite cũ trên máy chủ khi hệ thống đã chuyển sang chạy trên Oracle."""
    require_role(ctx, Role.ADMIN)
    engine = get_recon_engine()

    # Ràng buộc bắt buộc: Chỉ cho phép xóa khi ứng dụng đang chạy trên Oracle
    if engine.dialect.name == "sqlite":
        raise ServiceError(
            ErrorCode.FORBIDDEN,
            "Ứng dụng vẫn đang chạy trên cơ sở dữ liệu SQLite nguồn. "
            "Chỉ được xóa bản lưu SQLite cũ sau khi ứng dụng đã chuyển sang chạy trên Oracle.",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    mig_id = None
    if target_sqlite_path:
        target_file = Path(target_sqlite_path)
    else:
        with engine.connect() as conn:
            mig_row = (
                conn.execute(
                    select(recon_metadata_migration)
                    .where(
                        recon_metadata_migration.c.STATUS == "DONE",
                        recon_metadata_migration.c.OLD_SQLITE_DELETED_AT.is_(None),
                    )
                    .order_by(recon_metadata_migration.c.ID.desc())
                )
                .mappings()
                .first()
            )

        if mig_row is None or not mig_row.get("OLD_SQLITE_PATH"):
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy bản lưu SQLite cũ cần xóa.")

        mig_id = mig_row["ID"]
        target_file = Path(mig_row["OLD_SQLITE_PATH"])

    if confirm_filename.strip() != target_file.name:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Tên file xác nhận '{confirm_filename}' không khớp với tên file bản lưu '{target_file.name}'.",
        )

    file_size = 0
    if target_file.exists():
        file_size = target_file.stat().st_size
        target_file.unlink()

    # Ghi nhận vào migration table, purge log và audit log
    with engine.begin() as conn:
        if mig_id is not None:
            conn.execute(
                update(recon_metadata_migration)
                .where(recon_metadata_migration.c.ID == mig_id)
                .values(OLD_SQLITE_DELETED_AT=now)
            )

        conn.execute(
            recon_purge_log.insert().values(
                SCOPE="OLD_SQLITE",
                FILTER_JSON={"path": str(target_file)},
                RUN_COUNT=0,
                ROWS_DELETED=0,
                BYTES_FREED=file_size,
                ACTOR=ctx.username,
                CREATED_AT=now,
            )
        )

        write_audit_log(
            conn=conn,
            entity="OLD_SQLITE",
            entity_id=str(target_file),
            action="PURGE_TEMP",
            actor=ctx.username,
            new_data={"bytes_freed": file_size},
            now=now,
        )

    return {
        "deleted_file": str(target_file),
        "bytes_freed": file_size,
        "deleted_at": now.isoformat(),
    }
