"""Service Report export — task 26, spec 12 §6, 12b luồng E.

Queue/worker export (bước 1), streaming fetchmany + write-only XLSX (bước 2),
split/zip/hash/storage (bước 3), download/history/cache/security (bước 4).
"""

from __future__ import annotations

import csv
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import xlsxwriter
from sqlalchemy import Connection, select

from app.core.config import get_settings
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_report_run, recon_rpt_export
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.report_run import (
    build_run_query,
    load_version_detail,
    map_oracle_error,
    stable_order_by,
)
from app.services.report_source import open_checked_connection

MAX_RUNNING_PER_USER = 2
FETCH_BATCH_SIZE = 5000
MAX_ROWS_PER_FILE = 1_000_000


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _export_dir(export_id: int) -> Path:
    return (
        Path(get_settings().RECON_STORAGE_DIR) / "report_exports" / str(export_id)
    )


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
        "created_by": str(row["CREATED_BY"]),
        "created_at": row["CREATED_AT"],
        "finished_at": row["FINISHED_AT"],
        "error_message": row["ERROR_MESSAGE"],
    }


def _load_export_row(conn: Connection, export_id: int) -> Any:
    row = (
        conn.execute(
            select(recon_rpt_export).where(recon_rpt_export.c.ID == export_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy export.")
    return row


def _load_run_row_owned(conn: Connection, run_id: int, ctx: Ctx, admin: bool) -> Any:
    """Đọc run; người thường chỉ thấy run của mình (luồng G)."""
    row = (
        conn.execute(
            select(recon_report_run).where(recon_report_run.c.ID == run_id)
        )
        .mappings()
        .first()
    )
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
def request_export(
    ctx: Ctx, run_id: int, format: str, force: bool = False
) -> dict[str, Any]:
    """Đưa run DONE vào hàng đợi export (T26-01, Q7 cache)."""
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
        if run["STATUS"] != "DONE":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ export được run DONE; run chưa chạy xong.",
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
                or (
                    cached["FILE_PATH"]
                    and Path(str(cached["FILE_PATH"])).exists()
                )
            ):
                return _export_dict(cached)
        now = _now()
        res = conn.execute(
            recon_rpt_export.insert().values(
                RUN_ID=run_id,
                FORMAT=fmt,
                STATUS="QUEUED",
                PART_COUNT=1,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
            )
        )
        export_id = int(res.lastrowid)
        row = _load_export_row(conn, export_id)
        return _export_dict(row)


# ─── Ghi file (bước 1: CSV + XLSX cơ bản; bước 2: ghi theo type) ───────────


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


class _XlsxWriter:
    """Ghi XLSX stream qua XlsxWriter constant_memory (T26-03)."""

    def __init__(self, path: Path, headers: list[str]) -> None:
        self._wb = xlsxwriter.Workbook(str(path), {"constant_memory": True})
        self._ws = self._wb.add_worksheet("Data")
        self._row = 0
        for col, header in enumerate(headers):
            self._ws.write(0, col, header)
        self._row = 1

    def write_rows(self, rows: list[dict[str, Any]], fields: list[str]) -> None:
        for row in rows:
            for col, field in enumerate(fields):
                self._ws.write(self._row, col, row.get(field))
            self._row += 1

    def close(self) -> None:
        self._wb.close()


def _make_writer(format: str, path: Path, headers: list[str]) -> Any:
    if format == "CSV":
        return _CsvWriter(path, headers)
    return _XlsxWriter(path, headers)


def _iter_batches(
    detail: dict[str, Any],
    resolved: dict[str, Any],
    batch_size: int = FETCH_BATCH_SIZE,
) -> Iterator[tuple[list[str], list[dict[str, Any]]]]:
    """Stream kết quả theo lô fetchmany — giữ connection mở trong vòng lặp."""
    sql, binds = build_run_query(detail, resolved)
    order_by = stable_order_by(detail, [])
    ds_id = detail["data_source_id"]
    if ds_id is None:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, "Version chưa gắn Data Source."
        )
    data_timeout = int(detail["timeout_sec"])
    with open_checked_connection(ds_id, data_timeout) as ora_conn:
        cursor = ora_conn.cursor()
        try:
            cursor.execute(
                f"SELECT * FROM (\n{sql}\n) ORDER BY {order_by}", binds
            )
        except Exception as exc:
            raise map_oracle_error(exc, data_timeout) from exc
        col_names = [str(d[0]) for d in (cursor.description or [])]
        while True:
            batch = cursor.fetchmany(batch_size)
            if not batch:
                break
            yield col_names, [
                dict(zip(col_names, tuple(r), strict=False)) for r in batch
            ]


def _fail_export(engine: Any, export_id: int, error: ServiceError) -> None:
    with engine.begin() as conn:
        conn.execute(
            recon_rpt_export.update()
            .where(recon_rpt_export.c.ID == export_id)
            .values(
                STATUS="FAILED",
                ERROR_MESSAGE=error.message[:500],
                FINISHED_AT=_now(),
            )
        )


def execute_export(
    export_id: int,
    max_rows_per_file: int = MAX_ROWS_PER_FILE,
    engine: Any | None = None,
) -> dict[str, Any]:
    """Chạy một export QUEUED/RUNNING tới DONE/FAILED (worker gọi).

    Bước 1: một file duy nhất (split/zip ở bước 3). Lỗi giữa chừng → FAILED
    + xóa file dở.
    """
    eng = engine or get_recon_engine()
    with eng.connect() as conn:
        export = _load_export_row(conn, export_id)
        run = (
            conn.execute(
                select(recon_report_run).where(
                    recon_report_run.c.ID == int(export["RUN_ID"])
                )
            )
            .mappings()
            .first()
        )
        if run is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy run.")
        detail = load_version_detail(conn, int(run["VERSION_ID"]))
        resolved = dict(run["PARAMS_JSON"] or {})
    fmt = str(export["FORMAT"])
    out_dir = _export_dir(export_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "xlsx" if fmt == "XLSX" else "csv"
    out_path = out_dir / f"part-001.{ext}"
    try:
        columns = [c for c in detail["columns"] if c["excel_visible"]]
        fields = [c["field_name"] for c in columns]
        headers = [c["label"] for c in columns]
        writer = _make_writer(fmt, out_path, headers)
        written = 0
        try:
            for _col_names, batch in _iter_batches(detail, resolved):
                writer.write_rows(batch, fields)
                written += len(batch)
        finally:
            writer.close()
        file_size = out_path.stat().st_size
        file_hash = _file_hash(out_path)
        with eng.begin() as conn:
            conn.execute(
                recon_rpt_export.update()
                .where(recon_rpt_export.c.ID == export_id)
                .values(
                    STATUS="DONE",
                    FILE_PATH=str(out_path),
                    FILE_SIZE=file_size,
                    FILE_HASH=file_hash,
                    PART_COUNT=1,
                    ROW_COUNT=written,
                    FINISHED_AT=_now(),
                )
            )
    except ServiceError as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        _fail_export(eng, export_id, exc)
        with eng.connect() as conn:
            return _export_dict(_load_export_row(conn, export_id))
    with eng.connect() as conn:
        return _export_dict(_load_export_row(conn, export_id))
