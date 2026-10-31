from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select, update

from app.core.config import get_settings
from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_app_setting,
    recon_audit_log,
    recon_excel_load,
    recon_excel_row,
    recon_file,
    recon_invalid_row,
    recon_purge_log,
    recon_result_diff,
    recon_result_row,
    recon_run,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.run import PurgeFilter
from app.services import service


def _get_dir_size(path: Path) -> int:
    """Tính tổng dung lượng (bytes) của một thư mục."""
    if not path.exists():
        return 0
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            p = Path(root) / f
            try:
                total += p.stat().st_size
            except Exception:
                pass
    return total


def _purge_run_internal(ctx: Ctx, run_id: int) -> tuple[int, int]:
    """Xóa dữ liệu tạm của một run theo Spec 04 mục 12 với cơ chế xử lý dữ liệu dùng chung an toàn."""
    engine = get_recon_engine()
    settings = get_settings()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.connect() as conn:
        run_row = conn.execute(select(recon_run).where(recon_run.c.ID == run_id)).mappings().first()
        if not run_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy run {run_id}.")

        if run_row["TEMP_PURGED_AT"] is not None:
            return 0, 0  # Đã xóa rồi

        excel_load_id = run_row["EXCEL_LOAD_ID"]
        file_id = run_row["FILE_ID"]

    rows_deleted = 0
    bytes_freed = 0

    # 1. Xóa storage/runs/<run_id>
    run_storage_dir = Path(settings.RECON_STORAGE_DIR) / "runs" / str(run_id)
    if run_storage_dir.exists():
        bytes_freed += _get_dir_size(run_storage_dir)
        shutil.rmtree(run_storage_dir, ignore_errors=True)

    with engine.begin() as conn:
        # 2. Kiểm tra dữ liệu dùng chung cho EXCEL_LOAD
        if excel_load_id:
            other_active_runs = (
                conn.execute(
                    select(func.count(recon_run.c.ID)).where(
                        recon_run.c.EXCEL_LOAD_ID == excel_load_id,
                        recon_run.c.ID != run_id,
                        recon_run.c.TEMP_PURGED_AT.is_(None),
                    )
                ).scalar()
                or 0
            )

            # Chỉ xóa RECON_EXCEL_ROW khi không còn run nào khác dùng chung
            if other_active_runs == 0:
                # Đếm số dòng sẽ xóa
                cnt = conn.execute(select(func.count()).where(recon_excel_row.c.LOAD_ID == excel_load_id)).scalar() or 0
                rows_deleted += cnt
                bytes_freed += cnt * 150  # Ước tính 150 bytes / dòng

                # Xóa các dòng trong RECON_EXCEL_ROW
                conn.execute(delete(recon_excel_row).where(recon_excel_row.c.LOAD_ID == excel_load_id))

                # Đánh dấu PURGED_AT trên RECON_EXCEL_LOAD
                conn.execute(
                    update(recon_excel_load).where(recon_excel_load.c.ID == excel_load_id).values(PURGED_AT=now)
                )

                # Kiểm tra tiếp FILE_ID: còn EXCEL_LOAD nào khác của file chưa bị xóa không?
                if file_id:
                    other_active_loads = (
                        conn.execute(
                            select(func.count(recon_excel_load.c.ID)).where(
                                recon_excel_load.c.FILE_ID == file_id,
                                recon_excel_load.c.PURGED_AT.is_(None),
                            )
                        ).scalar()
                        or 0
                    )

                    if other_active_loads == 0:
                        f_rec = conn.execute(select(recon_file).where(recon_file.c.ID == file_id)).mappings().first()
                        if f_rec and f_rec["STORAGE_PATH"]:
                            file_p = Path(str(f_rec["STORAGE_PATH"]))
                            if file_p.exists():
                                bytes_freed += file_p.stat().st_size
                                try:
                                    file_p.unlink()
                                except Exception:
                                    pass
                        conn.execute(
                            update(recon_file)
                            .where(recon_file.c.ID == file_id)
                            .values(PURGED_AT=now, STORAGE_PATH=None)
                        )

        # 3. Cập nhật RECON_RUN đã xóa dữ liệu tạm
        conn.execute(
            update(recon_run)
            .where(recon_run.c.ID == run_id)
            .values(
                TEMP_PURGED_AT=now,
                TEMP_PURGED_BY=ctx.username,
            )
        )

        # 4. Ghi audit log
        conn.execute(
            recon_audit_log.insert().values(
                ENTITY="RECON_RUN",
                ENTITY_ID=str(run_id),
                ACTION="PURGE_TEMP",
                OLD_JSON=None,
                NEW_JSON={"purged_by": ctx.username, "rows_deleted": rows_deleted, "bytes_freed": bytes_freed},
                ACTOR=ctx.username,
                CREATED_AT=now,
            )
        )

    return rows_deleted, bytes_freed


@service
def mark_checked(
    ctx: Ctx,
    run_id: int,
    purge: bool = False,
) -> dict[str, Any]:
    """Đánh dấu một run là 'Đã kiểm tra xong' và tùy chọn xóa dữ liệu tạm của run."""
    require_role(ctx, Role.OPERATOR, Role.TEMPLATE_OWNER, Role.ADMIN)
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.connect() as conn:
        run_row = conn.execute(select(recon_run).where(recon_run.c.ID == run_id)).mappings().first()
        if not run_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy run {run_id}.")

        if run_row["STATUS"] in ("QUEUED", "RUNNING"):
            raise ServiceError(
                ErrorCode.RUN_BUSY,
                "Không thể đánh dấu kiểm tra cho run đang ở trạng thái chạy hoặc trong hàng đợi.",
            )

    with engine.begin() as conn:
        conn.execute(
            update(recon_run)
            .where(recon_run.c.ID == run_id)
            .values(
                CHECKED_BY=ctx.username,
                CHECKED_AT=now,
            )
        )

    if purge:
        _purge_run_internal(ctx, run_id)

    return {
        "run_id": run_id,
        "is_checked": True,
        "purged": purge,
        "checked_by": ctx.username,
        "checked_at": now.isoformat(),
    }


@service
def usage(ctx: Ctx) -> dict[str, Any]:
    """Giám sát dung lượng dữ liệu tạm và số lượng run chưa kiểm tra hoặc quá hạn cảnh báo."""
    settings = get_settings()
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Tính dung lượng ổ cứng
    files_dir = Path(settings.RECON_STORAGE_DIR) / "files"
    runs_dir = Path(settings.RECON_STORAGE_DIR) / "runs"
    disk_bytes = _get_dir_size(files_dir) + _get_dir_size(runs_dir)

    # 2. Đọc cài đặt cảnh báo
    warn_gb = 5.0
    warn_days = 30
    with engine.connect() as conn:
        s_gb = conn.execute(select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "TEMP_WARN_GB")).scalar()
        if s_gb:
            try:
                warn_gb = float(s_gb)
            except Exception:
                pass

        s_days = conn.execute(
            select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "TEMP_WARN_DAYS")
        ).scalar()
        if s_days:
            try:
                warn_days = int(s_days)
            except Exception:
                pass

        # Đếm các chỉ số
        excel_rows_count = conn.execute(select(func.count(recon_excel_row.c.LOAD_ID))).scalar() or 0
        unchecked_count = (
            conn.execute(select(func.count(recon_run.c.ID)).where(recon_run.c.CHECKED_AT.is_(None))).scalar() or 0
        )
        unpurged_count = (
            conn.execute(select(func.count(recon_run.c.ID)).where(recon_run.c.TEMP_PURGED_AT.is_(None))).scalar() or 0
        )

        overdue_threshold = now - timedelta(days=warn_days)
        overdue_count = (
            conn.execute(
                select(func.count(recon_run.c.ID)).where(
                    recon_run.c.TEMP_PURGED_AT.is_(None),
                    recon_run.c.CREATED_AT < overdue_threshold,
                )
            ).scalar()
            or 0
        )

    total_est_bytes = disk_bytes + (excel_rows_count * 150)
    is_warn = (total_est_bytes > warn_gb * 1024 * 1024 * 1024) or (overdue_count > 0)
    warn_gb_fmt = f"{total_est_bytes / (1024 * 1024 * 1024):.1f}".replace(".", ",")

    warning_msg = None
    if is_warn:
        warning_msg = f"Dữ liệu tạm {warn_gb_fmt} GB, {overdue_count} run giữ quá {warn_days} ngày. Xem và xóa"

    return {
        "total_bytes": total_est_bytes,
        "disk_bytes": disk_bytes,
        "excel_rows_count": excel_rows_count,
        "runs_unchecked_count": unchecked_count,
        "runs_unpurged_count": unpurged_count,
        "runs_overdue_count": overdue_count,
        "warn_gb": warn_gb,
        "warn_days": warn_days,
        "is_warning": is_warn,
        "warning_message": warning_msg,
    }


@service
def preview(ctx: Ctx, filter: PurgeFilter) -> dict[str, Any]:
    """Xem trước số run, số dòng và dung lượng sẽ giải phóng trước khi xóa."""
    require_role(ctx, Role.ADMIN)
    engine = get_recon_engine()

    with engine.connect() as conn:
        stmt = select(recon_run).where(
            recon_run.c.TEMP_PURGED_AT.is_(None),
            recon_run.c.STATUS.in_(["DONE", "FAILED", "CANCELLED"]),
        )
        if filter.only_checked:
            stmt = stmt.where(recon_run.c.CHECKED_AT.is_not(None))
        if filter.template_id:
            stmt = stmt.where(recon_run.c.TEMPLATE_ID == filter.template_id)
        if filter.before_date:
            stmt = stmt.where(recon_run.c.CREATED_AT <= filter.before_date)
        if filter.created_by:
            stmt = stmt.where(recon_run.c.CREATED_BY == filter.created_by)

        matching_runs = conn.execute(stmt).mappings().fetchall()
        run_ids = [int(r["ID"]) for r in matching_runs]

        est_rows = 0
        load_ids = [r["EXCEL_LOAD_ID"] for r in matching_runs if r["EXCEL_LOAD_ID"]]
        if load_ids:
            est_rows = (
                conn.execute(
                    select(func.coalesce(func.sum(recon_excel_load.c.ROWS_READ), 0)).where(
                        recon_excel_load.c.ID.in_(load_ids)
                    )
                ).scalar()
                or 0
            )

        est_bytes = (est_rows * 150) + (len(run_ids) * 1024 * 100)

    return {
        "run_count": len(run_ids),
        "run_ids": run_ids,
        "rows_estimated": int(est_rows),
        "bytes_estimated": int(est_bytes),
    }


def _purge_runs_core(
    ctx: Ctx,
    run_ids: list[int],
    scope: str = "RUNS",
    filter_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hàm nội bộ thực thi xóa danh sách run, thu hồi dung lượng và ghi nhận đúng 1 bản ghi purge log."""
    engine = get_recon_engine()

    # Kiểm tra không có run nào đang QUEUED hoặc RUNNING
    with engine.connect() as conn:
        busy_runs = conn.execute(
            select(recon_run.c.ID).where(
                recon_run.c.ID.in_(run_ids),
                recon_run.c.STATUS.in_(["QUEUED", "RUNNING"]),
            )
        ).fetchall()
        if busy_runs:
            raise ServiceError(
                ErrorCode.RUN_BUSY,
                f"Không thể xóa dữ liệu tạm của các run đang chạy hoặc trong hàng đợi: {[b[0] for b in busy_runs]}.",
            )

    total_rows = 0
    total_bytes = 0

    for r_id in run_ids:
        r_del, b_free = _purge_run_internal(ctx, r_id)
        total_rows += r_del
        total_bytes += b_free

    # Thu hồi dung lượng SQLite nếu đang dùng SQLite
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            try:
                conn.exec_driver_sql("PRAGMA incremental_vacuum")
            except Exception:
                pass

    # Ghi nhận RECON_PURGE_LOG
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            recon_purge_log.insert().values(
                SCOPE=scope,
                FILTER_JSON=filter_json or {"run_ids": run_ids},
                RUN_COUNT=len(run_ids),
                ROWS_DELETED=total_rows,
                BYTES_FREED=total_bytes,
                ACTOR=ctx.username,
                CREATED_AT=now,
            )
        )

    return {
        "runs_purged": len(run_ids),
        "rows_deleted": total_rows,
        "bytes_freed": total_bytes,
    }


@service
def purge_runs(ctx: Ctx, run_ids: list[int]) -> dict[str, Any]:
    """Xóa dữ liệu tạm cho danh sách các run được chọn (chỉ dành cho Quản trị viên)."""
    require_role(ctx, Role.ADMIN)
    return _purge_runs_core(ctx, run_ids, scope="RUNS", filter_json={"run_ids": run_ids})


@service
def purge_filter(
    ctx: Ctx,
    filter: PurgeFilter,
    confirm_text: str,
) -> dict[str, Any]:
    """Xóa dữ liệu tạm theo bộ lọc điều kiện với từ khóa xác nhận bắt buộc 'XOA'."""
    require_role(ctx, Role.ADMIN)

    if confirm_text != "XOA":
        raise ServiceError(
            ErrorCode.PURGE_CONFIRM_MISMATCH,
            "Từ khóa xác nhận không khớp. Bạn cần nhập chính xác 'XOA' để thực hiện thao tác xóa dữ liệu tạm.",
        )

    prev_res = preview(ctx, filter)
    if not prev_res.ok or not prev_res.data:
        raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không thể xác định danh sách run cần xóa.")

    run_ids = prev_res.data.get("run_ids", [])
    if not run_ids:
        return {"runs_purged": 0, "rows_deleted": 0, "bytes_freed": 0}

    return _purge_runs_core(
        ctx,
        run_ids,
        scope="FILTER",
        filter_json=filter.model_dump(mode="json"),
    )


@service
def purge_results(
    ctx: Ctx,
    older_than_days: int,
    confirm_text: str,
) -> dict[str, Any]:
    """Xóa các bản ghi kết quả đối soát cũ quá số ngày chỉ định (mặc định tắt, chỉ ADMIN)."""
    require_role(ctx, Role.ADMIN)

    if confirm_text != "XOA":
        raise ServiceError(
            ErrorCode.PURGE_CONFIRM_MISMATCH,
            "Từ khóa xác nhận không khớp. Bạn cần nhập chính xác 'XOA' để tiếp tục.",
        )

    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    threshold = now - timedelta(days=older_than_days)

    with engine.connect() as conn:
        old_runs = conn.execute(select(recon_run.c.ID).where(recon_run.c.CREATED_AT < threshold)).fetchall()
        old_run_ids = [int(r[0]) for r in old_runs]

    if not old_run_ids:
        return {"runs_cleared": 0, "rows_deleted": 0}

    with engine.begin() as conn:
        conn.execute(delete(recon_result_diff).where(recon_result_diff.c.RUN_ID.in_(old_run_ids)))
        res_del = conn.execute(delete(recon_result_row).where(recon_result_row.c.RUN_ID.in_(old_run_ids)))
        conn.execute(delete(recon_invalid_row).where(recon_invalid_row.c.RUN_ID.in_(old_run_ids)))

        rows_deleted = res_del.rowcount or 0

        conn.execute(
            recon_purge_log.insert().values(
                SCOPE="RESULTS",
                FILTER_JSON={"older_than_days": older_than_days},
                RUN_COUNT=len(old_run_ids),
                ROWS_DELETED=rows_deleted,
                BYTES_FREED=rows_deleted * 200,
                ACTOR=ctx.username,
                CREATED_AT=now,
            )
        )

    return {"runs_cleared": len(old_run_ids), "rows_deleted": rows_deleted}
