"""Service thực thi Semantic Query (Task 108 Bước 4).

Nối Resolver (Bước 2) + Compiler (Bước 3) với Data Source thật:
preview giới hạn dòng, phân trang cho run, SQL debug chỉ ADMIN.

Quy tắc:
- Metadata version ACTIVE được cache bất biến theo ``version_id`` (bản ACTIVE
  không sửa được nên cache theo id là an toàn; ``invalidate_semantic_query_cache``
  dùng cho test/reset).
- ``org_scopes`` chỉ nhận từ phía server (caller tin cậy) — browser không bao
  giờ được tự khai scope; thiếu scope cho ORG_SCOPE_HOOK -> fail-closed.
- Chỉ ADMIN xem SQL debug; debug không chạy SQL và không lộ giá trị bind.
- Oracle: ``open_checked_connection`` với timeout preview ngắn + ``map_oracle_error``.
  SQLite: mở đúng FILE_PATH của Data Source (không có FILE_PATH thì nguồn là
  chính RECON_APP DB, theo hành vi ``open_checked_connection`` hiện có).
"""

from __future__ import annotations

import copy
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, select

from app.core.config import get_settings
from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source, recon_rpt_model_ver
from app.engine.semantic_planner import resolve_semantic_plan
from app.engine.semantic_sql import compile_semantic_query
from app.engine.sql_guard import check_report_sql
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.semantic_query import SemanticQueryIntent, SemanticQueryPlan, SemanticQueryResult
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.report_run import _check_prod_admin, map_oracle_error
from app.services.report_source import open_checked_connection
from app.services.semantic_model import load_version_bundle

_CACHE_LOCK = threading.Lock()
_MAX_CACHE_ENTRIES = 128
_VERSION_CACHE: OrderedDict[tuple[str, int], dict[str, Any]] = OrderedDict()

_MAX_FOR_RUN_PAGE_SIZE = 1000


def invalidate_semantic_query_cache(version_id: int | None = None) -> None:
    """Xóa cache metadata version (một version hoặc toàn bộ) — dùng cho test/reset."""
    with _CACHE_LOCK:
        if version_id is None:
            _VERSION_CACHE.clear()
        else:
            target = int(version_id)
            for k in [key for key in _VERSION_CACHE if key[1] == target]:
                _VERSION_CACHE.pop(k, None)


def _engine_cache_key(conn: Any) -> str:
    eng = getattr(conn, "engine", None)
    url = getattr(eng, "url", None)
    if url is not None and hasattr(url, "render_as_string"):
        return str(url.render_as_string(hide_password=True))
    return "default"


def _load_bundle_cached(conn: Any, version_id: int) -> dict[str, Any]:
    """Đọc bundle version ACTIVE qua cache bất biến (an toàn đa luồng + LRU).

    Nội dung version ACTIVE là bất biến, nhưng TRẠNG THÁI thì không: publish
    version mới sẽ chuyển version cũ sang ARCHIVED. Đọc lại STATUS mỗi lần
    (1 SELECT theo khóa chính) để ``resolve_semantic_plan`` không chạy nhầm
    version đã bị khóa chỉ vì bundle còn nằm trong cache.
    """
    cache_key = (_engine_cache_key(conn), int(version_id))
    with _CACHE_LOCK:
        cached = _VERSION_CACHE.get(cache_key)
        if cached is not None:
            _VERSION_CACHE.move_to_end(cache_key)
            cached_copy = copy.deepcopy(cached)
        else:
            cached_copy = None

    if cached_copy is None:
        bundle = load_version_bundle(conn, int(version_id))
        with _CACHE_LOCK:
            _VERSION_CACHE[cache_key] = copy.deepcopy(bundle)
            _VERSION_CACHE.move_to_end(cache_key)
            while len(_VERSION_CACHE) > _MAX_CACHE_ENTRIES:
                _VERSION_CACHE.popitem(last=False)
        return copy.deepcopy(bundle)

    status = conn.execute(
        select(recon_rpt_model_ver.c.STATUS).where(recon_rpt_model_ver.c.ID == int(version_id))
    ).scalar_one_or_none()
    if status is not None:
        cached_copy["version"]["status"] = str(status)
    return cached_copy


def _intent_from_payload(intent_payload: dict[str, Any] | SemanticQueryIntent) -> SemanticQueryIntent:
    if isinstance(intent_payload, SemanticQueryIntent):
        return intent_payload
    if not isinstance(intent_payload, dict):
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Intent phải là dict hoặc SemanticQueryIntent.")
    return SemanticQueryIntent(**intent_payload)


@contextmanager
def _open_semantic_source(ds_id: int, db_type: str, file_path: str | None, timeout_sec: int) -> Iterator[Any]:
    """Mở kết nối DBAPI read-only tới Data Source của model.

    Oracle: qua ``open_checked_connection`` (siết ``call_timeout`` + kiểm tra
    tài khoản chỉ đọc). SQLite có FILE_PATH: mở đúng file nguồn với
    ``PRAGMA query_only = ON`` và busy timeout; không có FILE_PATH: nguồn là
    chính RECON_APP DB.
    """
    if db_type == "SQLITE" and file_path:
        engine = create_engine(
            f"sqlite:///{Path(file_path).as_posix()}",
            connect_args={"timeout": max(int(timeout_sec), 1)},
        )
        try:
            raw = engine.raw_connection()
            try:
                cur = raw.cursor()
                try:
                    cur.execute("PRAGMA query_only = ON")
                finally:
                    cur.close()
                yield raw
            finally:
                raw.close()
        finally:
            engine.dispose()
    else:
        with open_checked_connection(ds_id, timeout_sec) as raw_conn:
            yield raw_conn


_VN_TZ = timezone(timedelta(hours=7))


def _parse_iso_datetime(raw: str) -> datetime:
    text = raw.strip()
    if not text:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Giá trị ngày giờ không được để trống.")
    norm = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        dt = datetime.fromisoformat(norm)
    except ValueError as exc:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Giá trị ngày giờ '{raw}' không đúng định dạng ISO (YYYY-MM-DD hoặc YYYY-MM-DDTHH:MM:SS).",
        ) from exc
    if dt.tzinfo is not None:
        return dt.astimezone(_VN_TZ).replace(tzinfo=None)
    return dt


def _prepare_binds(
    db_type: str,
    binds: dict[str, Any],
    bind_types: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Chuẩn hóa giá trị bind cho driver: SQLite dùng chuỗi ISO khớp DATE/DATETIME;
    Oracle đổi chuỗi ISO sang datetime cho Oracle Thin; bool -> 1/0 cho cả 2."""
    types = bind_types or {}
    out: dict[str, Any] = {}
    for key, value in binds.items():
        dtype = str(types.get(key) or "").upper()
        if isinstance(value, bool):
            out[key] = 1 if value else 0
        elif db_type == "SQLITE":
            if isinstance(value, datetime):
                out[key] = value.strftime("%Y-%m-%d" if dtype == "DATE" else "%Y-%m-%d %H:%M:%S")
            elif isinstance(value, date):
                out[key] = value.strftime("%Y-%m-%d")
            elif dtype in ("DATE", "DATETIME") and isinstance(value, str) and value.strip():
                parsed = _parse_iso_datetime(value)
                out[key] = parsed.strftime("%Y-%m-%d" if dtype == "DATE" else "%Y-%m-%d %H:%M:%S")
            else:
                out[key] = value
        else:
            if dtype in ("DATE", "DATETIME") and isinstance(value, str) and value.strip():
                out[key] = _parse_iso_datetime(value)
            elif isinstance(value, date) and not isinstance(value, datetime):
                out[key] = datetime(value.year, value.month, value.day)
            else:
                out[key] = value
    return out


def _execute_compiled(
    db_type: str,
    raw_conn: Any,
    sql: str,
    binds: dict[str, Any],
    timeout_sec: int,
    fetch_limit: int,
    bind_types: dict[str, str] | None = None,
) -> tuple[list[str], list[tuple[Any, ...]]]:
    """Chạy SQL đã biên dịch qua DBAPI cursor; trả (tên cột, các dòng)."""
    prepared = _prepare_binds(db_type, binds, bind_types)
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, prepared)
        columns = [str(d[0]) for d in (cursor.description or [])]
        rows = [tuple(r) for r in cursor.fetchmany(fetch_limit)]
        return columns, rows
    except ServiceError:
        raise
    except Exception as exc:
        if db_type == "ORACLE":
            raise map_oracle_error(exc, timeout_sec) from exc
        raise ServiceError(ErrorCode.SOURCE_QUERY_FAILED, f"Lỗi thực thi truy vấn nguồn SQLite: {exc}") from exc
    finally:
        try:
            cursor.close()
        except Exception:
            pass


def _load_plan(
    ctx: Ctx,
    intent: SemanticQueryIntent,
    *,
    org_scopes: dict[str, str | None] | None,
    preview_max_rows: int,
    chart_max_points: int,
    check_prod: bool,
    export_max_rows: int | None = None,
) -> tuple[dict[str, Any], SemanticQueryPlan, str, str | None, bool]:
    """Nạp bundle + kiểm quyền PROD + trạng thái Data Source + resolve + compile."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        bundle = _load_bundle_cached(conn, int(intent.model_version_id))
        ds_info = bundle.get("model", {}).get("data_source") or {}
        ds_id = int(bundle["model"]["data_source_id"])
        ds_row = (
            conn.execute(
                select(
                    recon_data_source.c.DB_TYPE,
                    recon_data_source.c.IS_ACTIVE,
                    recon_data_source.c.FILE_PATH,
                ).where(recon_data_source.c.ID == ds_id)
            )
            .mappings()
            .first()
        )
        db_type = str((ds_row["DB_TYPE"] if ds_row else None) or ds_info.get("db_type") or "").upper()
        is_ds_active = (
            str(ds_row["IS_ACTIVE"]).upper() == "Y"
            if ds_row is not None
            else bool(ds_info.get("is_active", True))
        )
        if not is_ds_active:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Data Source của mô hình đang bị vô hiệu hóa, không thể truy vấn.",
            )
        if db_type not in ("ORACLE", "SQLITE"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Data Source của mô hình có DB_TYPE không hỗ trợ: {db_type!r}.",
            )
        if check_prod:
            _check_prod_admin(conn, ds_id, admin)
        file_path: str | None = None
        if db_type == "SQLITE" and ds_row is not None and ds_row["FILE_PATH"] is not None:
            file_path = str(ds_row["FILE_PATH"]) or None
    resolved = resolve_semantic_plan(intent, bundle)
    plan = compile_semantic_query(
        resolved,
        intent,
        username=ctx.username,
        roles=[str(r) for r in ctx.roles],
        is_admin=admin,
        org_scopes=dict(org_scopes or {}),
        dialect=db_type,  # type: ignore[arg-type]
        preview_max_rows=preview_max_rows,
        chart_max_points=chart_max_points,
        export_max_rows=export_max_rows,
    )
    return bundle, plan, db_type, file_path, admin


def _rows_to_dicts(plan: SemanticQueryPlan, rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    names = [str(c["name"]) for c in plan.output_columns]
    return [dict(zip(names, tuple(r), strict=False)) for r in rows]


# ─── Preview ────────────────────────────────────────────────────────────────


@service
@requires_menu("report_center", "report_admin", "report_model", any_of=True)
def execute_semantic_preview(
    ctx: Ctx,
    intent_payload: dict[str, Any] | SemanticQueryIntent,
    request_seq: int | None = None,
    org_scopes: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Chạy preview semantic query (giới hạn dòng theo cấu hình preview)."""
    started = time.perf_counter()
    intent = _intent_from_payload(intent_payload)
    if request_seq is not None:
        if int(request_seq) < 0:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "request_seq phải >= 0.")
        intent = intent.model_copy(update={"request_seq": request_seq})
    settings = get_settings()
    _bundle, plan, db_type, file_path, _admin = _load_plan(
        ctx,
        intent,
        org_scopes=org_scopes,
        preview_max_rows=settings.PREVIEW_MAX_ROWS,
        chart_max_points=settings.CHART_MAX_POINTS,
        check_prod=True,
    )
    timeout_sec = int(settings.PREVIEW_TIMEOUT_SECONDS)
    with _open_semantic_source(int(_bundle["model"]["data_source_id"]), db_type, file_path, timeout_sec) as raw_conn:
        _columns, rows = _execute_compiled(
            db_type, raw_conn, plan.sql, plan.binds, timeout_sec, plan.row_limit, plan.bind_types
        )
    row_dicts = _rows_to_dicts(plan, rows)
    if plan.fetch_extra_row:
        truncated = len(row_dicts) > int(settings.CHART_MAX_POINTS)
        if truncated:
            row_dicts = row_dicts[: int(settings.CHART_MAX_POINTS)]
    else:
        # TABLE/KPI: đánh dấu khi đạt đúng trần giới hạn preview (tránh phá contract LIMIT N).
        truncated = len(row_dicts) >= plan.row_limit
    warnings = list(plan.warnings)
    result = SemanticQueryResult(
        columns=plan.output_columns,
        rows=row_dicts,
        row_count=len(row_dicts),
        truncated=truncated,
        warning_message="; ".join(warnings) if warnings else None,
        request_seq=intent.request_seq,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
    return result.model_dump()


# ─── Chạy cho Report Run (Task 109) ─────────────────────────────────────────


@service
@requires_menu("report_center")
def execute_semantic_query_for_run(
    ctx: Ctx,
    model_version_id: int,
    intent_payload: dict[str, Any] | SemanticQueryIntent,
    page: int = 1,
    page_size: int = 100,
    org_scopes: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Chạy semantic query phân trang cho Report Run; trả kèm ``total``."""
    started = time.perf_counter()
    if int(page) < 1:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page phải >= 1.")
    if int(page_size) < 1 or int(page_size) > _MAX_FOR_RUN_PAGE_SIZE:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, f"page_size phải từ 1 đến {_MAX_FOR_RUN_PAGE_SIZE}.")
    payload = dict(intent_payload) if isinstance(intent_payload, dict) else intent_payload.model_dump()
    if "model_version_id" in payload and int(payload["model_version_id"]) != int(model_version_id):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "model_version_id trong intent không khớp với model_version_id của run.",
        )
    payload["model_version_id"] = int(model_version_id)
    intent = SemanticQueryIntent(**payload)
    intent = intent.model_copy(
        update={
            "limit": int(page_size),
            "offset": (int(page) - 1) * int(page_size),
            "visual_type": "TABLE",
        }
    )
    settings = get_settings()
    bundle, plan, db_type, file_path, _admin = _load_plan(
        ctx,
        intent,
        org_scopes=org_scopes,
        # Giới hạn preview không áp cho run: nới trần lên đúng page_size.
        preview_max_rows=max(int(page_size), int(settings.PREVIEW_MAX_ROWS)),
        chart_max_points=settings.CHART_MAX_POINTS,
        check_prod=True,
    )
    timeout_sec = int(settings.RUN_DB_CALL_TIMEOUT_SECONDS)
    count_sql = f'SELECT COUNT(*) FROM ({plan.base_sql}) "t_count"'
    ok, reason, _discovered = check_report_sql(count_sql)
    if not ok:
        raise ServiceError(ErrorCode.SQL_NOT_ALLOWED, reason or "SQL đếm total không được phép.")
    ds_id = int(bundle["model"]["data_source_id"])
    with _open_semantic_source(ds_id, db_type, file_path, timeout_sec) as raw_conn:
        _cols, count_rows = _execute_compiled(
            db_type, raw_conn, count_sql, plan.binds, timeout_sec, 1, plan.bind_types
        )
        total = int(count_rows[0][0]) if count_rows else 0
        _columns, rows = _execute_compiled(
            db_type, raw_conn, plan.sql, plan.binds, timeout_sec, plan.row_limit, plan.bind_types
        )
    row_dicts = _rows_to_dicts(plan, rows)
    result = SemanticQueryResult(
        columns=plan.output_columns,
        rows=row_dicts,
        row_count=len(row_dicts),
        truncated=False,
        warning_message="; ".join(plan.warnings) if plan.warnings else None,
        request_seq=intent.request_seq,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
    data = result.model_dump()
    data["total"] = total
    data["page"] = int(page)
    data["page_size"] = int(page_size)
    return data


# ─── Stream cho Export (Task 109 Bước 5) ───────────────────────────────────


def open_semantic_export_stream(
    ctx: Ctx,
    model_version_id: int,
    intent_payload: dict[str, Any] | SemanticQueryIntent,
    *,
    batch_size: int = 5000,
    max_rows: int = 1_000_000,
    timeout_sec: int = 300,
    org_scopes: dict[str, str | None] | None = None,
) -> tuple[list[dict[str, Any]], Iterator[list[dict[str, Any]]]]:
    """Biên dịch intent 1 lần cho export; trả (output_columns, iterator lô).

    output_columns: [{name, label, data_type}] để caller dựng writer trước
    khi stream. Iterator mở 1 kết nối và 1 cursor duy nhất, stream qua
    ``fetchmany`` theo ``batch_size`` tới khi hết dữ liệu hoặc đủ
    ``max_rows`` (tránh lặp OFFSET/mở connection nhiều lần). SQL qua
    ``check_report_sql`` (fail-closed); RLS ép theo Ctx chủ export.
    """
    if int(batch_size) < 1:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "batch_size phải >= 1.")
    if int(max_rows) < 1:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "max_rows phải >= 1.")
    payload = dict(intent_payload) if isinstance(intent_payload, dict) else intent_payload.model_dump()
    if "model_version_id" in payload and int(payload["model_version_id"]) != int(model_version_id):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "model_version_id trong intent không khớp với model_version_id của run.",
        )
    payload["model_version_id"] = int(model_version_id)
    base_intent = _intent_from_payload(payload)
    base_intent = base_intent.model_copy(update={"visual_type": "TABLE", "offset": 0})
    settings = get_settings()
    bundle, plan, db_type, file_path, _admin = _load_plan(
        ctx,
        base_intent,
        org_scopes=org_scopes,
        preview_max_rows=settings.PREVIEW_MAX_ROWS,
        chart_max_points=settings.CHART_MAX_POINTS,
        check_prod=True,
        export_max_rows=int(max_rows),
    )
    ok, reason, _discovered = check_report_sql(plan.sql)
    if not ok:
        raise ServiceError(ErrorCode.SQL_NOT_ALLOWED, reason or "SQL export không được phép.")
    ds_id = int(bundle["model"]["data_source_id"])
    columns = [
        {
            "name": str(c["name"]),
            "label": str(c.get("label") or c["name"]),
            "data_type": str(c.get("data_type") or "STRING"),
        }
        for c in plan.output_columns
    ]

    def _batches() -> Iterator[list[dict[str, Any]]]:
        fetched = 0
        with _open_semantic_source(ds_id, db_type, file_path, int(timeout_sec)) as raw_conn:
            prepared = _prepare_binds(db_type, plan.binds, plan.bind_types)
            cursor = raw_conn.cursor()
            try:
                cursor.execute(plan.sql, prepared)
                col_names = [str(d[0]) for d in (cursor.description or [])]
                while fetched < int(max_rows):
                    to_fetch = min(int(batch_size), int(max_rows) - fetched)
                    batch = cursor.fetchmany(to_fetch)
                    if not batch:
                        break
                    rows = [dict(zip(col_names, tuple(r), strict=False)) for r in batch]
                    fetched += len(rows)
                    yield rows
            except ServiceError:
                raise
            except Exception as exc:
                if db_type == "ORACLE":
                    raise map_oracle_error(exc, int(timeout_sec)) from exc
                raise ServiceError(
                    ErrorCode.SOURCE_QUERY_FAILED,
                    f"Lỗi thực thi truy vấn nguồn SQLite: {exc}",
                ) from exc
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass

    return columns, _batches()


# ─── SQL Debug (ADMIN) ──────────────────────────────────────────────────────


@service
@requires_menu("report_admin")
def get_semantic_sql_debug(
    ctx: Ctx,
    intent_payload: dict[str, Any] | SemanticQueryIntent,
    org_scopes: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Trả SQL read-only đã biên dịch + TÊN bind param (không lộ giá trị, không chạy SQL)."""
    require_role(ctx, Role.ADMIN)
    intent = _intent_from_payload(intent_payload)
    settings = get_settings()
    _bundle, plan, db_type, _file_path, _admin = _load_plan(
        ctx,
        intent,
        org_scopes=org_scopes,
        preview_max_rows=settings.PREVIEW_MAX_ROWS,
        chart_max_points=settings.CHART_MAX_POINTS,
        check_prod=False,  # debug không chạm dữ liệu nên không cần rào PROD
    )
    return {
        "sql": plan.sql,
        "binds": sorted(plan.binds.keys()),
        "dialect": db_type,
        "primary_fact_table_id": plan.primary_fact_table_id,
        "tables_used": plan.tables_used,
        "output_columns": plan.output_columns,
        "rls_applied": plan.rls_applied,
        "warnings": plan.warnings,
    }
