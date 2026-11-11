"""Service Report export — task 26, spec 12 §6, 12b luồng E.

Queue/worker export (bước 1), streaming fetchmany + write-only XLSX (bước 2),
split/zip/hash/storage (bước 3), download/history/cache/security (bước 4).
"""

from __future__ import annotations

import csv
import hashlib
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import xlsxwriter
from sqlalchemy import Connection, delete, select

from app.core.audit import write_audit_log
from app.core.config import get_settings
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_report, recon_report_run, recon_rpt_export
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.report_run import (
    _prepare_query_binds,
    build_run_query,
    create_report_run,
    execute_report_run,
    load_version_detail,
    map_oracle_error,
    stable_order_by,
)
from app.services.report_source import open_checked_connection

MAX_RUNNING_PER_USER = 10  # Task 57: mặc định song song (setting
# EXPORT_MAX_CONCURRENT, trang Cài đặt hệ thống) cũng là 10 — 1 con số
# duy nhất cho cả code và setting.
FETCH_BATCH_SIZE = 5000
MAX_ROWS_PER_FILE = 1_000_000


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _export_dir(export_id: int) -> Path:
    return Path(get_settings().RECON_STORAGE_DIR) / "report_exports" / str(export_id)


def _delete_export_files(export_id: int) -> None:
    """Xóa thư mục file của 1 export (cả file đơn lẫn các part ZIP)."""
    shutil.rmtree(_export_dir(export_id), ignore_errors=True)


def _export_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "run_id": int(row["RUN_ID"]),
        "format": str(row["FORMAT"]),
        "status": str(row["STATUS"]),
        "file_path": row["FILE_PATH"],
        "file_size": row["FILE_SIZE"],
        "file_hash": row["FILE_HASH"],
        "part_count": int(row["PART_COUNT"]),
        "row_count": row["ROW_COUNT"],
        "progress_pct": int(row["PROGRESS_PCT"] or 0),
        "progress_step": row["PROGRESS_STEP"],
        "created_by": str(row["CREATED_BY"]),
        "created_at": row["CREATED_AT"],
        "finished_at": row["FINISHED_AT"],
        "error_message": row["ERROR_MESSAGE"],
    }


def _load_export_row(conn: Connection, export_id: int) -> Any:
    row = conn.execute(select(recon_rpt_export).where(recon_rpt_export.c.ID == export_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy export.")
    return row


def _load_run_row_owned(conn: Connection, run_id: int, ctx: Ctx, admin: bool) -> Any:
    """Đọc run; người thường chỉ thấy run của mình (luồng G)."""
    row = conn.execute(select(recon_report_run).where(recon_report_run.c.ID == run_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy run.")
    if not admin and row["CREATED_BY"] != ctx.username:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy run.")
    return row


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ─── Bước 1: Queue ─────────────────────────────────────────────────────────


@service
@requires_menu("report_center")
def request_export(ctx: Ctx, run_id: int, format: str, force: bool = False) -> dict[str, Any]:
    """Đưa run DONE hoặc QUEUED vào hàng đợi export (T26-01, Q7 cache).

    Task 54: run QUEUED (vừa tạo, chưa chạy báo cáo) cũng được phép —
    worker tự chạy query theo PARAMS_JSON đã lưu và stream, không cần
    run DONE trước; chỉ mất % thật khi chưa biết tổng dòng (worker ước
    lượng theo batch). RUNNING/FAILED/CANCELLED vẫn bị từ chối.
    """
    fmt = (format or "").strip().upper()
    if fmt not in ("XLSX", "CSV"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Định dạng export phải là XLSX hoặc CSV (ZIP chỉ là kết quả khi split).",
        )
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.begin() as conn:
        run = _load_run_row_owned(conn, run_id, ctx, admin)
        if run["STATUS"] not in ("QUEUED", "DONE"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ export được run đã chạy xong hoặc đang chờ chạy.",
            )
        if not force:
            # Cache (Q7): DONE export cùng run+format (file đơn) được trả lại;
            # export đang QUEUED/RUNNING cùng run+format cũng trả lại (tránh
            # xếp trùng). Export ZIP (FORMAT='ZIP', đã split) không dùng làm cache.
            cached = (
                conn.execute(
                    select(recon_rpt_export)
                    .where(
                        recon_rpt_export.c.RUN_ID == run_id,
                        recon_rpt_export.c.FORMAT == fmt,
                        recon_rpt_export.c.STATUS.in_(("QUEUED", "RUNNING", "DONE")),
                    )
                    .order_by(recon_rpt_export.c.CREATED_AT.desc())
                )
                .mappings()
                .first()
            )
            if cached is not None and (
                cached["STATUS"] in ("QUEUED", "RUNNING")
                or (cached["FILE_PATH"] and Path(str(cached["FILE_PATH"])).exists())
            ):
                return _export_dict(cached)
        now = _now()
        res = conn.execute(
            recon_rpt_export.insert().values(
                RUN_ID=run_id,
                FORMAT=fmt,
                STATUS="QUEUED",
                PART_COUNT=1,
                PROGRESS_PCT=0,
                PROGRESS_STEP=None,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
            )
        )
        export_id = int(res.lastrowid)
        write_audit_log(
            conn,
            "RECON_RPT_EXPORT",
            export_id,
            "REQUEST_EXPORT",
            ctx.username,
            new_data={"run_id": run_id, "format": fmt},
        )
        row = _load_export_row(conn, export_id)
        return _export_dict(row)


@service
@requires_menu("report_center")
def rerun_and_export(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Xuất lại (task 52): chạy lại báo cáo với cùng tham số (run mới,
    dữ liệu mới) rồi đưa export mới vào hàng đợi chạy ngầm.

    Run của viewer chạy đồng bộ trong web process (count + 1 trang) nên
    tạo → chạy → xuất làm liền trong một lần gọi, không cần cột cờ hay
    hook worker. Version theo ACTIVE như "Chạy lại" (task 43). Định dạng
    export theo export mới nhất của run gốc (ZIP → XLSX), mặc định XLSX.
    """
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.begin() as conn:
        orig = _load_run_row_owned(conn, run_id, ctx, admin)
        latest = (
            conn.execute(
                select(recon_rpt_export)
                .where(recon_rpt_export.c.RUN_ID == run_id)
                .order_by(recon_rpt_export.c.CREATED_AT.desc(), recon_rpt_export.c.ID.desc())
            )
            .mappings()
            .first()
        )
    fmt = "XLSX"
    if latest is not None:
        fmt = str(latest["FORMAT"] or "XLSX")
        if fmt == "ZIP":
            fmt = "XLSX"
    params = dict(orig["PARAMS_JSON"]) if isinstance(orig["PARAMS_JSON"], dict) else {}
    created = create_report_run(
        ctx, int(orig["REPORT_ID"]), template_id=int(orig["TEMPLATE_ID"]), values=params
    )
    if not created.ok or not isinstance(created.data, dict):
        raise ServiceError(ErrorCode.INTERNAL_ERROR, created.message or "Không tạo được run mới.")
    new_run_id = int(created.data["id"])
    executed = execute_report_run(ctx, new_run_id)
    if not executed.ok or not isinstance(executed.data, dict):
        raise ServiceError(ErrorCode.INTERNAL_ERROR, executed.message or "Chạy báo cáo lỗi.")
    run = executed.data.get("run") or {}
    if run.get("status") != "DONE":
        detail = run.get("error_message") or "Run lỗi, chưa rõ nguyên nhân."
        raise ServiceError(ErrorCode.INTERNAL_ERROR, f"Chạy báo cáo lỗi: {detail}")
    exp = request_export(ctx, new_run_id, fmt)
    if not exp.ok or not isinstance(exp.data, dict):
        raise ServiceError(ErrorCode.INTERNAL_ERROR, exp.message or "Không tạo được export.")
    with engine.begin() as conn:
        write_audit_log(
            conn,
            "RECON_REPORT_RUN",
            new_run_id,
            "RERUN_AND_EXPORT",
            ctx.username,
            new_data={"from_run_id": run_id, "export_id": int(exp.data["id"]), "format": fmt},
        )
    return {"run_id": new_run_id, "export": exp.data}


# ─── Bước 4: Download/history/cache/security ────────────────────────────────


def _load_export_row_owned(conn: Connection, export_id: int, ctx: Ctx, admin: bool) -> Any:
    row = _load_export_row(conn, export_id)
    if not admin and row["CREATED_BY"] != ctx.username:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy export.")
    return row


def _load_export_row_own(conn: Connection, export_id: int, ctx: Ctx) -> Any:
    """Chỉ chủ sở hữu (kể cả ADMIN cũng chỉ tác động export của mình)."""
    row = _load_export_row(conn, export_id)
    if row["CREATED_BY"] != ctx.username:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy export.")
    return row


@service
@requires_menu("report_center")
def list_exports(
    ctx: Ctx,
    run_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Lịch sử export, owner scope (luồng G)."""
    if page < 1 or page_size < 1 or page_size > 200:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page >= 1, page_size 1..200.")
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        stmt = select(recon_rpt_export)
        count_stmt = select(recon_rpt_export.c.ID)
        if not admin:
            stmt = stmt.where(recon_rpt_export.c.CREATED_BY == ctx.username)
            count_stmt = count_stmt.where(recon_rpt_export.c.CREATED_BY == ctx.username)
        if run_id is not None:
            stmt = stmt.where(recon_rpt_export.c.RUN_ID == run_id)
            count_stmt = count_stmt.where(recon_rpt_export.c.RUN_ID == run_id)
        total = len(conn.execute(count_stmt).fetchall())
        rows = (
            conn.execute(
                stmt.order_by(
                    recon_rpt_export.c.CREATED_AT.desc(),
                    recon_rpt_export.c.ID.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .mappings()
            .all()
        )
        return {
            "exports": [_export_dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@service
@requires_menu("report_center")
def get_export(ctx: Ctx, export_id: int) -> dict[str, Any]:
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        return _export_dict(_load_export_row_owned(conn, export_id, ctx, admin))


@service
@requires_menu("report_center")
def download_export(ctx: Ctx, export_id: int) -> dict[str, Any]:
    """Trả thông tin file để tải (T26-10/11)."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        export = _load_export_row_owned(conn, export_id, ctx, admin)
    if export["STATUS"] != "DONE":
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Export chưa xong, chưa tải được.")
    file_path = export["FILE_PATH"]
    if not file_path or not Path(str(file_path)).exists():
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            "File xuất đã không còn (đã xóa/hết hạn). Hãy export lại.",
        )
    with engine.begin() as conn:
        write_audit_log(
            conn,
            "RECON_RPT_EXPORT",
            export_id,
            "DOWNLOAD_EXPORT",
            ctx.username,
            new_data={"run_id": int(export["RUN_ID"]), "format": str(export["FORMAT"])},
        )
    return {
        "export_id": int(export["ID"]),
        "run_id": int(export["RUN_ID"]),
        "format": str(export["FORMAT"]),
        "file_path": str(file_path),
        "file_name": Path(str(file_path)).name,
        "file_size": export["FILE_SIZE"],
        "file_hash": export["FILE_HASH"],
    }


@service
@requires_menu("report_center")
def retry_export(ctx: Ctx, export_id: int) -> dict[str, Any]:
    """Chạy lại export FAILED (T26-09); chỉ chủ sở hữu (kể cả ADMIN)."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        export = _load_export_row_own(conn, export_id, ctx)
        if export["STATUS"] != "FAILED":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ chạy lại được export FAILED.",
            )
        conn.execute(
            recon_rpt_export.update()
            .where(recon_rpt_export.c.ID == export_id)
            .values(
                STATUS="QUEUED",
                FILE_PATH=None,
                FILE_SIZE=None,
                FILE_HASH=None,
                PART_COUNT=1,
                ROW_COUNT=None,
                PROGRESS_PCT=0,
                PROGRESS_STEP=None,
                ERROR_MESSAGE=None,
                FINISHED_AT=None,
            )
        )
        write_audit_log(conn, "RECON_RPT_EXPORT", export_id, "RETRY_EXPORT", ctx.username)
        return _export_dict(_load_export_row(conn, export_id))


@service
@requires_menu("report_center")
def cancel_export(ctx: Ctx, export_id: int) -> dict[str, Any]:
    """Hủy export QUEUED/RUNNING; chỉ chủ sở hữu (kể cả ADMIN)."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        export = _load_export_row_own(conn, export_id, ctx)
        if export["STATUS"] not in ("QUEUED", "RUNNING"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ hủy được export đang chờ hoặc đang chạy.",
            )
        conn.execute(
            recon_rpt_export.update()
            .where(recon_rpt_export.c.ID == export_id)
            .values(STATUS="CANCELLED", FINISHED_AT=_now())
        )
        write_audit_log(conn, "RECON_RPT_EXPORT", export_id, "CANCEL_EXPORT", ctx.username)
        return _export_dict(_load_export_row(conn, export_id))


@service
@requires_menu("report_admin")
def delete_export(ctx: Ctx, export_id: int) -> dict[str, Any]:
    """Xóa hẳn export đã kết thúc (DONE/FAILED/CANCELLED) — chỉ ADMIN (task 52).

    Xóa file trên đĩa + dòng export, ghi audit. Không xóa export đang
    QUEUED/RUNNING (worker có thể đang ghi file) và không xóa run.
    """
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN xóa được file export.")
    with engine.begin() as conn:
        export = _load_export_row(conn, export_id)
        if export["STATUS"] not in ("DONE", "FAILED", "CANCELLED"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ xóa được export đã kết thúc (DONE/FAILED/CANCELLED).",
            )
        _delete_export_files(export_id)
        conn.execute(delete(recon_rpt_export).where(recon_rpt_export.c.ID == export_id))
        write_audit_log(conn, "RECON_RPT_EXPORT", export_id, "DELETE_EXPORT", ctx.username)
        return {"id": export_id, "deleted": True}


def _is_cancelled(engine: Any, export_id: int) -> bool:
    with engine.connect() as conn:
        status = conn.execute(
            select(recon_rpt_export.c.STATUS).where(recon_rpt_export.c.ID == export_id)
        ).scalar_one_or_none()
    return bool(status == "CANCELLED")


class _CsvWriter:
    """Ghi CSV stream: BOM UTF-8, cùng vòng fetchmany (T26-05)."""

    def __init__(self, path: Path, headers: list[str]) -> None:
        self._fh = path.open("w", encoding="utf-8-sig", newline="")
        self._writer = csv.writer(self._fh)
        self._writer.writerow(headers)

    def write_rows(self, rows: list[dict[str, Any]], fields: list[str]) -> None:
        for row in rows:
            self._writer.writerow([row.get(f) for f in fields])

    def close(self) -> None:
        self._fh.close()


def _to_datetime(value: Any) -> datetime | None:
    """Chuỗi ISO/ngày giờ Oracle → datetime; không parse được → None."""
    from datetime import date as _date

    if isinstance(value, datetime):
        return value
    if isinstance(value, _date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class _XlsxWriter:
    """Ghi XLSX stream qua XlsxWriter constant_memory (T26-03).

    Ghi theo type (bước 2): STRING → write_string (giữ leading zero,
    T26-04), NUMBER → write_number + num_format từ FORMAT_MASK,
    DATE/DATETIME → write_datetime + num_format từ FORMAT_MASK.
    """

    def __init__(self, path: Path, columns: list[dict[str, Any]]) -> None:
        self._wb = xlsxwriter.Workbook(str(path), {"constant_memory": True})
        self._ws = self._wb.add_worksheet("Data")
        self._dtypes = [c["data_type"] for c in columns]
        self._formats: list[Any] = []
        header_fmt = self._wb.add_format({"bold": True})
        for col, column in enumerate(columns):
            dtype = column["data_type"]
            mask = column.get("format_mask")
            fmt_kwargs: dict[str, Any] = {}
            align = str(column.get("alignment") or "").lower()
            if align in ("left", "center", "right"):
                fmt_kwargs["align"] = align
            if dtype == "STRING":
                fmt_kwargs["num_format"] = "@"
            elif dtype == "NUMBER":
                if mask:
                    fmt_kwargs["num_format"] = mask
            elif dtype == "DATE":
                fmt_kwargs["num_format"] = mask or "YYYY-MM-DD"
            elif dtype == "DATETIME":
                fmt_kwargs["num_format"] = mask or "YYYY-MM-DD HH:mm:ss"
            self._formats.append(self._wb.add_format(fmt_kwargs))
            self._ws.write(0, col, column["label"], header_fmt)
            width = column.get("width")
            if width:
                self._ws.set_column(col, col, int(width) / 7)
        self._row = 1

    def _write_cell(self, row: int, col: int, value: Any, dtype: str, fmt: Any) -> None:
        if value is None:
            self._ws.write_blank(row, col, None, fmt)
            return
        if dtype == "STRING":
            self._ws.write_string(row, col, str(value), fmt)
        elif dtype == "NUMBER":
            try:
                num = value if isinstance(value, (int, float)) else float(str(value))
                self._ws.write_number(row, col, num, fmt)
            except (TypeError, ValueError):
                self._ws.write_string(row, col, str(value), fmt)
        elif dtype in ("DATE", "DATETIME"):
            dt = _to_datetime(value)
            if dt is not None:
                self._ws.write_datetime(row, col, dt, fmt)
            else:
                self._ws.write_string(row, col, str(value), fmt)
        else:
            self._ws.write(row, col, value, fmt)

    def write_rows(self, rows: list[dict[str, Any]], fields: list[str]) -> None:
        for row in rows:
            for col, field in enumerate(fields):
                self._write_cell(
                    self._row,
                    col,
                    row.get(field),
                    self._dtypes[col],
                    self._formats[col],
                )
            self._row += 1

    def close(self) -> None:
        self._wb.close()


def _make_writer(format: str, path: Path, columns: list[dict[str, Any]]) -> Any:
    if format == "CSV":
        return _CsvWriter(path, [c["label"] for c in columns])
    return _XlsxWriter(path, columns)


def _iter_batches(
    detail: dict[str, Any],
    resolved: dict[str, Any],
    batch_size: int = FETCH_BATCH_SIZE,
) -> Iterator[tuple[list[str], list[dict[str, Any]]]]:
    """Stream kết quả theo lô fetchmany — giữ connection mở trong vòng lặp."""
    sql, raw_binds = build_run_query(detail, resolved)
    binds = _prepare_query_binds(detail, raw_binds)
    order_by = stable_order_by(detail, [])
    ds_id = detail["data_source_id"]
    if ds_id is None:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Version chưa gắn Data Source.")
    data_timeout = int(detail["timeout_sec"])
    with open_checked_connection(ds_id, data_timeout) as ora_conn:
        cursor = ora_conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM (\n{sql}\n) ORDER BY {order_by}", binds)
        except Exception as exc:
            raise map_oracle_error(exc, data_timeout) from exc
        col_names = [str(d[0]) for d in (cursor.description or [])]
        while True:
            batch = cursor.fetchmany(batch_size)
            if not batch:
                break
            yield col_names, [dict(zip(col_names, tuple(r), strict=False)) for r in batch]


def _update_export_progress(engine: Any, export_id: int, pct: int, step: str) -> None:
    """Ghi % + bước hiện tại xuống DB để UI poll đọc được (task 40).

    % kẹp 0..100; mỗi lần ghi là một transaction ngắn riêng (worker chạy
    trong tiến trình khác với app nên không dùng chung transaction).
    """
    pct = max(0, min(100, int(pct)))
    with engine.begin() as conn:
        conn.execute(
            recon_rpt_export.update()
            .where(recon_rpt_export.c.ID == export_id)
            .values(PROGRESS_PCT=pct, PROGRESS_STEP=step)
        )


def _fail_export(engine: Any, export_id: int, error: ServiceError) -> None:
    with engine.begin() as conn:
        actor = conn.execute(
            select(recon_rpt_export.c.CREATED_BY).where(recon_rpt_export.c.ID == export_id)
        ).scalar_one_or_none()
        conn.execute(
            recon_rpt_export.update()
            .where(recon_rpt_export.c.ID == export_id)
            .values(
                STATUS="FAILED",
                ERROR_MESSAGE=error.message[:500],
                PROGRESS_STEP=f"Lỗi: {error.message[:100]}",
                FINISHED_AT=_now(),
            )
        )
        write_audit_log(
            conn,
            "RECON_RPT_EXPORT",
            export_id,
            "EXECUTE_EXPORT",
            str(actor or "worker"),
            new_data={
                "status": "FAILED",
                "error_code": str(error.code),
                "error_message": error.message[:500],
            },
        )


def _summary_text(
    report_code: str,
    run_id: int,
    export_id: int,
    fmt: str,
    total_rows: int,
    part_count: int,
    part_names: list[str],
    max_rows_per_file: int,
) -> str:
    lines = [
        f"Báo cáo: {report_code}",
        f"Run: {run_id}",
        f"Export: {export_id}",
        f"Định dạng: {fmt}",
        f"Tổng số dòng: {total_rows}",
        f"Số file: {part_count}",
        f"Mỗi file tối đa: {max_rows_per_file} dòng",
        f"Thời gian xuất: {_now().isoformat()}",
        "Các file:",
    ]
    lines.extend(f"  - {name}" for name in part_names)
    return "\n".join(lines) + "\n"


def _zip_parts(
    out_dir: Path,
    part_paths: list[Path],
    summary: str,
    export_id: int,
) -> Path:
    """Zip các part + _summary.txt; xóa part gốc sau khi zip xong."""
    zip_path = out_dir / f"export-{export_id}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for part in part_paths:
            zf.write(part, arcname=part.name)
        zf.writestr("_summary.txt", summary)
    for part in part_paths:
        part.unlink(missing_ok=True)
    return zip_path


def execute_export(
    export_id: int,
    max_rows_per_file: int = MAX_ROWS_PER_FILE,
    engine: Any | None = None,
) -> dict[str, Any]:
    """Chạy một export QUEUED/RUNNING tới DONE/FAILED (worker gọi).

    Bước 3: split 1.000.000 dòng/file (mặc định), >1 part → ZIP (parts +
    _summary.txt). Lỗi giữa chừng → FAILED + xóa file dở.
    """
    eng = engine or get_recon_engine()
    with eng.connect() as conn:
        export = _load_export_row(conn, export_id)
        run = (
            conn.execute(select(recon_report_run).where(recon_report_run.c.ID == int(export["RUN_ID"])))
            .mappings()
            .first()
        )
        if run is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy run.")
        detail = load_version_detail(conn, int(run["VERSION_ID"]))
        resolved = dict(run["PARAMS_JSON"] or {})
        report_code = conn.execute(
            select(recon_report.c.CODE).where(recon_report.c.ID == int(run["REPORT_ID"]))
        ).scalar_one_or_none() or str(run["REPORT_ID"])
    fmt = str(export["FORMAT"])
    out_dir = _export_dir(export_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "xlsx" if fmt == "XLSX" else "csv"
    total_rows = int(run["ROW_COUNT"] or 0)
    try:
        _update_export_progress(eng, export_id, 5, "Đang chuẩn bị")
        columns = [c for c in detail["columns"] if c["excel_visible"]]
        fields = [c["field_name"] for c in columns]
        part = 1
        part_paths = [out_dir / f"part-{part:03d}.{ext}"]
        writer = _make_writer(fmt, part_paths[0], columns)
        written = 0
        written_in_part = 0
        batch_no = 0
        last_pct = 10
        _update_export_progress(eng, export_id, 10, "Đang truy vấn dữ liệu")
        try:
            for _col_names, batch in _iter_batches(detail, resolved):
                batch_no += 1
                # Checkpoint hủy (bước 4): kiểm tra mỗi 10 batch.
                if batch_no % 10 == 0 and _is_cancelled(eng, export_id):
                    writer.close()
                    shutil.rmtree(out_dir, ignore_errors=True)
                    with eng.connect() as conn:
                        return _export_dict(_load_export_row(conn, export_id))
                offset = 0
                while offset < len(batch):
                    if written_in_part >= max_rows_per_file:
                        writer.close()
                        part += 1
                        part_paths.append(out_dir / f"part-{part:03d}.{ext}")
                        writer = _make_writer(fmt, part_paths[-1], columns)
                        written_in_part = 0
                    room = max_rows_per_file - written_in_part
                    chunk = batch[offset : offset + room]
                    writer.write_rows(chunk, fields)
                    written += len(chunk)
                    written_in_part += len(chunk)
                    offset += len(chunk)
                if total_rows > 0:
                    pct = 10 + int(75 * written / total_rows)
                    step = f"Đang ghi file Excel: {written} / {total_rows} dòng"
                else:
                    # Task 54: run QUEUED chưa có tổng dòng — % ước lượng
                    # theo batch, text không hiện "/ 0 dòng".
                    pct = min(85, 10 + batch_no * 5)
                    step = f"Đang ghi file Excel: {written} dòng"
                pct = min(85, pct)
                if pct != last_pct:
                    last_pct = pct
                    _update_export_progress(
                        eng,
                        export_id,
                        pct,
                        step,
                    )
        finally:
            writer.close()
        if part > 1:
            _update_export_progress(eng, export_id, 90, "Đang nén file")
        else:
            _update_export_progress(eng, export_id, 90, "Đang hoàn tất file")
        if part > 1:
            summary = _summary_text(
                report_code,
                int(run["ID"]),
                export_id,
                fmt,
                written,
                part,
                [p.name for p in part_paths],
                max_rows_per_file,
            )
            final_path = _zip_parts(out_dir, part_paths, summary, export_id)
            final_format = "ZIP"
        else:
            final_path = part_paths[0]
            final_format = fmt
        file_size = final_path.stat().st_size
        file_hash = _file_hash(final_path)
        with eng.begin() as conn:
            conn.execute(
                recon_rpt_export.update()
                .where(recon_rpt_export.c.ID == export_id)
                .values(
                    STATUS="DONE",
                    FORMAT=final_format,
                    FILE_PATH=str(final_path),
                    FILE_SIZE=file_size,
                    FILE_HASH=file_hash,
                    PART_COUNT=part,
                    ROW_COUNT=written,
                    PROGRESS_PCT=100,
                    PROGRESS_STEP="Hoàn tất",
                    FINISHED_AT=_now(),
                )
            )
            # Task 54: run QUEUED (nộp chạy ngầm khi chưa Xem) thì chốt
            # luôn thành DONE + tổng dòng đã ghi — Lịch sử hiện "Hoàn
            # tất" thay vì "Đang chờ" mãi. UPDATE có điều kiện nên không
            # đụng run DONE đã có ROW_COUNT từ viewer.
            conn.execute(
                recon_report_run.update()
                .where(recon_report_run.c.ID == int(run["ID"]))
                .where(recon_report_run.c.STATUS == "QUEUED")
                .values(STATUS="DONE", ROW_COUNT=written, FINISHED_AT=_now())
            )
            write_audit_log(
                conn,
                "RECON_RPT_EXPORT",
                export_id,
                "EXECUTE_EXPORT",
                str(export["CREATED_BY"]),
                new_data={
                    "status": "DONE",
                    "format": final_format,
                    "row_count": written,
                    "part_count": part,
                },
            )
    except ServiceError as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        _fail_export(eng, export_id, exc)
        with eng.connect() as conn:
            return _export_dict(_load_export_row(conn, export_id))
    with eng.connect() as conn:
        return _export_dict(_load_export_row(conn, export_id))
