"""Service chạy bộ — Bước 4 task 18 (tạo, tải file, ghép, tham số).

Các hàm bước 6/7 (precheck, start, retry, cancel, matrix, build_zip) ở
bước 6 và 7. Tạo lần chạy bộ (spec 10 mục 5.1), tải file lần chạy bộ
(mục 5.2), kiểm tra tham số (mục 5.3).
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection, Engine

from app.core.audit import write_audit_log
from app.core.config import get_settings
from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_batch_def,
    recon_batch_def_item,
    recon_batch_run,
    recon_batch_run_file,
    recon_batch_run_item,
    recon_data_source,
    recon_file,
    recon_run,
    recon_run_queue,
    recon_run_summary,
    recon_template,
    recon_template_version,
)
from app.engine.filters import apply_time_filter
from app.engine.mapping import detect_template
from app.engine.merge_files import merge_excel_files, sum_control_totals
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import TemplateConfig
from app.services import service
from app.services.batch_formula import parse_period, resolve_params
from app.services.batch_matcher import match as match_pattern
from app.services.batch_matcher import normalize_name
from app.services.file_service import upload_file
from app.services.perm import (
    check_owned,
    is_admin,
    owner_filter,
    requires_menu,
)
from app.services.run_service import export_run
from app.services.source_conn import open_source_connection

MAX_FILES_PER_RUN = 200
MAX_FILES_PER_ITEM = 50
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_ZIP_BYTES = 200 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_ZIP_ENTRIES = 200
EXCEL_EXTS = {".xlsx", ".xls", ".csv"}
ACCEPTED_EXTS = EXCEL_EXTS | {".zip"}

ALLOWED_EDITOR_ROLES = (Role.ADMIN, Role.TEMPLATE_OWNER, Role.OPERATOR)


def _parse_config(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else json.loads(str(raw))


def _parse_json(raw: Any, default: Any) -> Any:
    """Đọc cột JsonText: đã là dict/list thì dùng luôn, còn chuỗi thì parse."""
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    return json.loads(str(raw))


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _run_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "batch_def_id": int(row["BATCH_DEF_ID"]),
        "name": str(row["NAME"]),
        "period": str(row["PERIOD"]),
        "period_from": _iso(row["PERIOD_FROM"]),
        "period_to": _iso(row["PERIOD_TO"]),
        "status": str(row["STATUS"]),
        "include_warn": str(row["INCLUDE_WARN"]),
        "prod_confirmed_by": row["PROD_CONFIRMED_BY"],
        "cnt_items": int(row["CNT_ITEMS"]),
        "cnt_done": int(row["CNT_DONE"]),
        "cnt_failed": int(row["CNT_FAILED"]),
        "cnt_skipped": int(row["CNT_SKIPPED"]),
        "cnt_not_run": int(row["CNT_NOT_RUN"]),
        "zip_path": row["ZIP_PATH"],
        "zip_run_set_hash": row["ZIP_RUN_SET_HASH"],
        "started_at": _iso(row["STARTED_AT"]),
        "finished_at": _iso(row["FINISHED_AT"]),
        "created_by": str(row["CREATED_BY"]),
        "created_at": _iso(row["CREATED_AT"]),
        "updated_by": str(row["UPDATED_BY"]),
        "updated_at": _iso(row["UPDATED_AT"]),
        "row_version": int(row["ROW_VERSION"]),
    }


def _run_item_dict(row: Any, files: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "batch_run_id": int(row["BATCH_RUN_ID"]),
        "batch_def_item_id": int(row["BATCH_DEF_ITEM_ID"]),
        "template_id": int(row["TEMPLATE_ID"]),
        "template_version": int(row["TEMPLATE_VERSION"]) if row["TEMPLATE_VERSION"] is not None else None,
        "profile_code": str(row["PROFILE_CODE"]),
        "data_source_id": int(row["DATA_SOURCE_ID"]),
        "seq_no": int(row["SEQ_NO"]),
        "priority": int(row["PRIORITY"]),
        "multi_file": str(row["MULTI_FILE"]),
        "is_required": str(row["IS_REQUIRED"]),
        "status": str(row["STATUS"]),
        "skip_reason": row["SKIP_REASON"],
        "skipped_by": row["SKIPPED_BY"],
        "params_run_override": _parse_json(row["PARAMS_RUN_OVERRIDE_JSON"], {}),
        "params_resolved": _parse_json(row["PARAMS_RESOLVED_JSON"], {}),
        "precheck": _parse_json(row["PRECHECK_JSON"], None),
        "precheck_at": _iso(row["PRECHECK_AT"]),
        "current_run_id": int(row["CURRENT_RUN_ID"]) if row["CURRENT_RUN_ID"] is not None else None,
        "attempt_no": int(row["ATTEMPT_NO"]),
        "error_code": row["ERROR_CODE"],
        "error_msg": row["ERROR_MSG"],
        "created_by": str(row["CREATED_BY"]),
        "created_at": _iso(row["CREATED_AT"]),
        "updated_by": str(row["UPDATED_BY"]),
        "updated_at": _iso(row["UPDATED_AT"]),
        "files": files or [],
    }


def _run_file_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "batch_run_id": int(row["BATCH_RUN_ID"]),
        "batch_run_item_id": int(row["BATCH_RUN_ITEM_ID"]) if row["BATCH_RUN_ITEM_ID"] is not None else None,
        "file_id": int(row["FILE_ID"]),
        "from_zip_file_id": int(row["FROM_ZIP_FILE_ID"]) if row["FROM_ZIP_FILE_ID"] is not None else None,
        "original_name": str(row["ORIGINAL_NAME"]),
        "normalized_name": str(row["NORMALIZED_NAME"]),
        "match_state": str(row["MATCH_STATE"]),
        "match_by": row["MATCH_BY"],
        "candidate_item_ids": _parse_json(row["CANDIDATE_ITEM_IDS"], []),
        "sheet_name": row["SHEET_NAME"],
        "seq_in_item": int(row["SEQ_IN_ITEM"]) if row["SEQ_IN_ITEM"] is not None else None,
        "created_by": str(row["CREATED_BY"]),
        "created_at": _iso(row["CREATED_AT"]),
        "updated_by": str(row["UPDATED_BY"]),
        "updated_at": _iso(row["UPDATED_AT"]),
    }


def _load_items(conn: Connection, run_id: int, with_files: bool = True) -> list[dict[str, Any]]:
    item_rows = (
        conn.execute(
            select(recon_batch_run_item)
            .where(recon_batch_run_item.c.BATCH_RUN_ID == run_id)
            .order_by(recon_batch_run_item.c.PRIORITY, recon_batch_run_item.c.ID)
        )
        .mappings()
        .all()
    )
    file_rows = (
        conn.execute(
            select(recon_batch_run_file)
            .where(recon_batch_run_file.c.BATCH_RUN_ID == run_id)
            .order_by(recon_batch_run_file.c.ID)
        )
        .mappings()
        .all()
    )
    files_by_item: dict[int | None, list[dict[str, Any]]] = {}
    for f in file_rows:
        files_by_item.setdefault(f["BATCH_RUN_ITEM_ID"], []).append(_run_file_dict(dict(f)))
    template_ids = sorted({int(r["TEMPLATE_ID"]) for r in item_rows})
    code_map: dict[int, tuple[str, str]] = {}
    if template_ids:
        for t in (
            conn.execute(
                select(recon_template.c.ID, recon_template.c.CODE, recon_template.c.NAME).where(
                    recon_template.c.ID.in_(template_ids)
                )
            )
            .mappings()
            .all()
        ):
            code_map[int(t["ID"])] = (str(t["CODE"]), str(t["NAME"]))
    items = []
    for r in item_rows:
        d = _run_item_dict(dict(r), files_by_item.get(r["ID"], []) if with_files else [])
        code, name = code_map.get(int(r["TEMPLATE_ID"]), ("", ""))
        d["template_code"] = code
        d["template_name"] = name
        items.append(d)
    return items


def _load_files(conn: Connection, run_id: int) -> list[dict[str, Any]]:
    file_rows = (
        conn.execute(
            select(recon_batch_run_file)
            .where(recon_batch_run_file.c.BATCH_RUN_ID == run_id)
            .order_by(recon_batch_run_file.c.ID)
        )
        .mappings()
        .all()
    )
    return [_run_file_dict(dict(f)) for f in file_rows]


def _load_run_full(conn: Connection, run: dict[str, Any]) -> dict[str, Any]:
    out = _run_dict(run)
    out["items"] = _load_items(conn, run["ID"])
    out["files"] = _load_files(conn, run["ID"])
    def_row = _get_def(conn, int(run["BATCH_DEF_ID"]))
    out["def_code"] = str(def_row["CODE"])
    out["def_name"] = str(def_row["NAME"])
    return out


def _get_def(conn: Connection, def_id: int) -> dict[str, Any]:
    row = conn.execute(select(recon_batch_def).where(recon_batch_def.c.ID == def_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.BATCH_NOT_FOUND, f"Không tìm thấy bộ đối soát với id {def_id}.")
    return dict(row)


def _get_run(conn: Connection, run_id: int) -> dict[str, Any]:
    row = conn.execute(select(recon_batch_run).where(recon_batch_run.c.ID == run_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.BATCH_NOT_FOUND, f"Không tìm thấy lần chạy bộ với id {run_id}.")
    return dict(row)


def _get_run_item(conn: Connection, item_id: int) -> dict[str, Any]:
    row = conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.ID == item_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.BATCH_NOT_FOUND, f"Không tìm thấy mục chạy bộ với id {item_id}.")
    return dict(row)


def _check_run_editor(ctx: Ctx, run: dict[str, Any], engine: Engine) -> None:
    """Chỉ người tạo hoặc ADMIN được sửa lần chạy bộ."""
    require_role(ctx, *ALLOWED_EDITOR_ROLES)
    if not is_admin(ctx, engine=engine) and run["CREATED_BY"] != ctx.username:
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ người tạo lần chạy bộ hoặc ADMIN mới được sửa lần chạy này.")


def _require_draft(run: dict[str, Any]) -> None:
    if run["STATUS"] != "DRAFT":
        raise ServiceError(
            ErrorCode.BATCH_RUN_NOT_DRAFT,
            "Lần chạy bộ đã bắt đầu hoặc đã kết thúc, không thể thay đổi.",
        )


def _resolve_profile_code(cfg: TemplateConfig, override: str | None) -> str:
    if override:
        return override
    for profile in cfg.profiles:
        if profile.is_default:
            return profile.code
    return cfg.profiles[0].code


def _serialize_params(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in params.items():
        out[key] = value.isoformat() if isinstance(value, datetime) else value
    return out


@service
@requires_menu("batch_run")
def create_batch_run(ctx: Ctx, batch_def_id: int, period: str, name: str | None = None) -> dict[str, Any]:
    """Tạo lần chạy bộ (DRAFT) cho bộ đang ACTIVE với kỳ tháng YYYY-MM.

    Snapshot: template, version ACTIVE lúc tạo, profile, Data Source, tham số
    đã giải với kỳ (spec 10 mục 5.1). Mục có template đã lưu trữ được tạo
    ở trạng thái SKIPPED/TEMPLATE_ARCHIVED.
    """
    require_role(ctx, *ALLOWED_EDITOR_ROLES)
    period_from, period_to = parse_period(period)
    engine = get_recon_engine()

    with engine.begin() as conn:
        batch_def = _get_def(conn, batch_def_id)
        if batch_def["STATUS"] != "ACTIVE":
            raise ServiceError(ErrorCode.BATCH_NOT_ACTIVE, "Bộ đối soát chưa kích hoạt, không thể tạo lần chạy.")
        period_warning = (
            conn.execute(
                select(recon_batch_run.c.ID)
                .where(recon_batch_run.c.BATCH_DEF_ID == batch_def_id)
                .where(recon_batch_run.c.PERIOD == period)
                .limit(1)
            ).first()
            is not None
        )
        def_items = (
            conn.execute(
                select(recon_batch_def_item)
                .where(recon_batch_def_item.c.BATCH_DEF_ID == batch_def_id)
                .where(recon_batch_def_item.c.IS_ACTIVE == "Y")
                .order_by(recon_batch_def_item.c.PRIORITY, recon_batch_def_item.c.ID)
            )
            .mappings()
            .all()
        )
        default_name = f"Tháng {int(period[5:7])}/{period[:4]}"
        run_id = conn.execute(
            insert(recon_batch_run).values(
                BATCH_DEF_ID=batch_def_id,
                NAME=name or default_name,
                PERIOD=period,
                PERIOD_FROM=period_from,
                PERIOD_TO=period_to,
                STATUS="DRAFT",
                INCLUDE_WARN="N",
                CNT_ITEMS=0,
                CNT_DONE=0,
                CNT_FAILED=0,
                CNT_SKIPPED=0,
                CNT_NOT_RUN=0,
                CREATED_BY=ctx.username,
                CREATED_AT=_now(),
                UPDATED_BY=ctx.username,
                UPDATED_AT=_now(),
                ROW_VERSION=1,
            )
        ).lastrowid
        run_id = int(run_id)
        items: list[dict[str, Any]] = []
        for def_item in def_items:
            tmpl_row = conn.execute(
                select(recon_template.c.STATUS).where(recon_template.c.ID == def_item["TEMPLATE_ID"])
            ).first()
            if tmpl_row is None:
                raise ServiceError(
                    ErrorCode.BATCH_NOT_FOUND,
                    f"Không tìm thấy template với id {def_item['TEMPLATE_ID']}.",
                )
            archived = tmpl_row[0] == "ARCHIVED"
            version_query = (
                select(recon_template_version)
                .where(recon_template_version.c.TEMPLATE_ID == def_item["TEMPLATE_ID"])
                .order_by(recon_template_version.c.VERSION.desc())
                .limit(1)
            )
            if not archived:
                version_query = version_query.where(recon_template_version.c.STATUS == "ACTIVE")
            version_row = conn.execute(version_query).mappings().first()
            if version_row is None:
                raise ServiceError(
                    ErrorCode.BATCH_TEMPLATE_NOT_ACTIVE,
                    f"Template id {def_item['TEMPLATE_ID']} không có version đang hoạt động.",
                )
            cfg = TemplateConfig.model_validate(_parse_config(version_row["CONFIG_JSON"]))
            ds_id = def_item["DATA_SOURCE_ID"] or version_row["DATA_SOURCE_ID"]
            if ds_id is None:
                raise ServiceError(
                    ErrorCode.NOT_FOUND,
                    f"Template id {def_item['TEMPLATE_ID']} chưa được cấu hình Data Source nguồn.",
                )
            profile_code = _resolve_profile_code(cfg, def_item["PROFILE_CODE"])
            def_override = _parse_json(def_item["PARAMS_OVERRIDE_JSON"], {})
            run_override: dict[str, Any] = {}
            resolved = resolve_params(cfg.db_source.params, def_override, run_override, period)
            item_id = conn.execute(
                insert(recon_batch_run_item).values(
                    BATCH_RUN_ID=run_id,
                    BATCH_DEF_ITEM_ID=def_item["ID"],
                    TEMPLATE_ID=def_item["TEMPLATE_ID"],
                    TEMPLATE_VERSION=int(version_row["VERSION"]),
                    PROFILE_CODE=profile_code,
                    DATA_SOURCE_ID=int(ds_id),
                    SEQ_NO=int(def_item["SEQ_NO"]),
                    PRIORITY=def_item["PRIORITY"],
                    MULTI_FILE=def_item["MULTI_FILE"],
                    IS_REQUIRED=def_item["IS_REQUIRED"],
                    PARAMS_RUN_OVERRIDE_JSON=json.dumps(run_override, ensure_ascii=False),
                    PARAMS_RESOLVED_JSON=json.dumps(_serialize_params(resolved), ensure_ascii=False),
                    STATUS="SKIPPED" if archived else "PENDING",
                    SKIP_REASON="TEMPLATE_ARCHIVED" if archived else None,
                    SKIPPED_BY=None,
                    CREATED_BY=ctx.username,
                    CREATED_AT=_now(),
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=_now(),
                )
            ).lastrowid
            item_row = (
                conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.ID == int(item_id)))
                .mappings()
                .first()
            )
            assert item_row is not None
            items.append(_run_item_dict(dict(item_row)))

        conn.execute(update(recon_batch_run).where(recon_batch_run.c.ID == run_id).values(CNT_ITEMS=len(items)))
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN",
            entity_id=run_id,
            action="CREATE_BATCH_RUN",
            actor=ctx.username,
            new_data={"batch_def_id": batch_def_id, "period": period, "name": name or default_name},
            now=_now(),
        )
        out = _run_dict(_get_run(conn, run_id))
        out["items"] = items
        out["files"] = []
        out["period_warning"] = period_warning
        return out


@service
@requires_menu("batch_run")
def list_active_defs(ctx: Ctx) -> list[dict[str, Any]]:
    """Bộ đối soát đang ACTIVE để chọn ở bước 1 wizard (mọi role có menu batch_run).

    Không dùng list_batch_defs vì service đó yêu cầu menu batch_def mà
    OPERATOR không có (spec 11a).
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(recon_batch_def).where(recon_batch_def.c.STATUS == "ACTIVE").order_by(recon_batch_def.c.CODE)
            )
            .mappings()
            .all()
        )
        return [
            {
                "id": int(r["ID"]),
                "code": str(r["CODE"]),
                "name": str(r["NAME"]),
                "max_parallel_per_ds": int(r["MAX_PARALLEL_PER_DS"]),
            }
            for r in rows
        ]


@service
@requires_menu("batch_run")
def get_batch_run(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Lấy chi tiết lần chạy bộ kèm các mục và file đã tải."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        run = check_owned(conn, recon_batch_run, "ID", run_id, ctx, engine=engine)
        return _load_run_full(conn, dict(run))


@service
@requires_menu("batch_run")
def list_batch_runs(
    ctx: Ctx,
    def_id: int | None = None,
    status: str | None = None,
    period: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Liệt kê lần chạy bộ có phân trang theo owner scope (Q2, task 18)."""
    engine = get_recon_engine()
    scope = owner_filter(ctx, engine)
    base = (
        select(
            recon_batch_run,
            recon_batch_def.c.CODE.label("DEF_CODE"),
            recon_batch_def.c.NAME.label("DEF_NAME"),
        )
        .select_from(recon_batch_run.join(recon_batch_def, recon_batch_run.c.BATCH_DEF_ID == recon_batch_def.c.ID))
        .order_by(recon_batch_run.c.ID.desc())
    )
    if not scope["is_admin"]:
        base = base.where(recon_batch_run.c.CREATED_BY == scope["username"])
    if def_id:
        base = base.where(recon_batch_run.c.BATCH_DEF_ID == def_id)
    if status:
        base = base.where(recon_batch_run.c.STATUS == status)
    if period:
        base = base.where(recon_batch_run.c.PERIOD == period)
    if q:
        base = base.where(recon_batch_run.c.NAME.like(f"%{q}%"))

    with engine.connect() as conn:
        total = len(conn.execute(base).all())
        page = max(page, 1)
        rows = conn.execute(base.offset((page - 1) * page_size).limit(page_size)).mappings().all()
        items = []
        for row in rows:
            d = _run_dict(dict(row))
            d["def_code"] = row["DEF_CODE"]
            d["def_name"] = row["DEF_NAME"]
            items.append(d)
        return {"items": items, "total": total, "page": page, "page_size": page_size}


def _store_zip_record(ctx: Ctx, filename: str, content: bytes, engine: Engine) -> dict[str, Any]:
    """Lưu file .zip vào RECON_FILE (file_service chỉ nhận Excel/CSV)."""
    from app.core.config import get_settings

    sha = hashlib.sha256(content).hexdigest()
    storage_dir = Path(get_settings().RECON_STORAGE_DIR) / "files"
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{sha}.zip"
    if not storage_path.exists():
        storage_path.write_bytes(content)
    now = _now()
    with engine.begin() as conn:
        file_id = conn.execute(
            insert(recon_file).values(
                ORIGINAL_NAME=filename,
                STORAGE_PATH=str(storage_path),
                SIZE_BYTES=len(content),
                SHA256=sha,
                SHEETS_JSON=None,
                UPLOADED_BY=ctx.username,
                UPLOADED_AT=now,
            )
        ).lastrowid
    return {"id": int(file_id), "sha256": sha, "size_bytes": len(content), "storage_path": str(storage_path)}


def _upload_single(ctx: Ctx, filename: str, content: bytes, engine: Engine) -> dict[str, Any]:
    """Tải một file Excel/CSV (qua upload_file) hoặc .zip (lưu trực tiếp)."""
    ext = Path(filename).suffix.lower()
    if len(content) > MAX_FILE_BYTES and ext != ".zip":
        raise ServiceError(
            ErrorCode.FILE_TOO_LARGE,
            f"File '{filename}' vượt quá giới hạn 50 MB.",
        )
    if ext == ".zip":
        if len(content) > MAX_ZIP_BYTES:
            raise ServiceError(
                ErrorCode.FILE_TOO_LARGE,
                f"File zip '{filename}' vượt quá giới hạn 200 MB.",
            )
        return _store_zip_record(ctx, filename, content, engine)
    res = upload_file(ctx, filename=filename, content=content)
    if not res.ok:
        raise ServiceError(res.code or ErrorCode.INTERNAL_ERROR, res.message or "Tải file thất bại.")
    if res.data is None:
        raise ServiceError(ErrorCode.INTERNAL_ERROR, "Tải file thất bại.")
    return dict(res.data)


def _extract_zip_entries(filename: str, content: bytes) -> tuple[list[tuple[str, bytes]], list[dict[str, Any]]]:
    """Giải nén .zip an toàn: chặn zip slip, zip bomb, chỉ nhận Excel/CSV.

    Trả về (entries, skipped): entries là [(tên, nội dung)], skipped là
    các mục bị bỏ qua kèm lý do (không phải Excel/CSV hoặc vượt 50 MB).
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ServiceError(ErrorCode.BATCH_ZIP_INVALID, f"File zip '{filename}' không hợp lệ hoặc bị hỏng.") from exc
    entries = zf.infolist()
    if len(entries) > MAX_ZIP_ENTRIES:
        raise ServiceError(
            ErrorCode.BATCH_ZIP_INVALID,
            f"File zip '{filename}' chứa quá {MAX_ZIP_ENTRIES} mục.",
        )
    total_uncompressed = 0
    out: list[tuple[str, bytes]] = []
    skipped: list[dict[str, Any]] = []
    for info in entries:
        name = info.filename
        if info.is_dir():
            continue
        parts = Path(name).parts
        if name.startswith("/") or name.startswith("\\") or ".." in parts:
            raise ServiceError(
                ErrorCode.BATCH_ZIP_INVALID,
                f"File zip '{filename}' chứa đường dẫn không hợp lệ: '{name}'.",
            )
        if any(part.startswith(".") for part in parts):
            continue
        ext = Path(name).suffix.lower()
        if ext not in EXCEL_EXTS:
            skipped.append(
                {
                    "filename": f"{filename}/{name}",
                    "reason": "BATCH_ZIP_INVALID",
                    "message": f"File '{name}' trong zip không phải Excel/CSV nên bị bỏ qua.",
                }
            )
            continue
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ServiceError(
                ErrorCode.BATCH_ZIP_INVALID,
                f"File zip '{filename}' giải nén vượt quá 1 GB.",
            )
        if info.file_size > MAX_FILE_BYTES:
            skipped.append(
                {
                    "filename": f"{filename}/{name}",
                    "reason": "FILE_TOO_LARGE",
                    "message": f"File '{name}' trong zip vượt quá giới hạn 50 MB nên bị bỏ qua.",
                }
            )
            continue
        out.append((name, zf.read(info.filename)))
    return out, skipped


def _match_item(
    conn: Connection, run_id: int, original_name: str, storage_path: str
) -> tuple[str, str | None, int | None, list[int]]:
    """Ghép file với mục: mẫu tên trước, header sau, không khớp thì UNMATCHED."""
    item_rows = (
        conn.execute(
            select(
                recon_batch_run_item.c.ID,
                recon_batch_run_item.c.TEMPLATE_ID,
                recon_batch_run_item.c.TEMPLATE_VERSION,
                recon_batch_def_item.c.FILE_PATTERN,
            )
            .select_from(
                recon_batch_run_item.join(
                    recon_batch_def_item,
                    recon_batch_run_item.c.BATCH_DEF_ITEM_ID == recon_batch_def_item.c.ID,
                )
            )
            .where(recon_batch_run_item.c.BATCH_RUN_ID == run_id)
            .where(recon_batch_run_item.c.STATUS == "PENDING")
        )
        .mappings()
        .all()
    )
    matched = match_pattern(
        original_name,
        [{"item_id": int(r["ID"]), "pattern": r["FILE_PATTERN"]} for r in item_rows],
    )
    if len(matched) == 1:
        return "MATCHED", "PATTERN", int(matched[0]), []
    if len(matched) > 1:
        return "AMBIGUOUS", None, None, [int(i) for i in matched]
    templates: list[dict[str, Any]] = []
    for r in item_rows:
        version_row = conn.execute(
            select(recon_template_version.c.CONFIG_JSON)
            .where(recon_template_version.c.TEMPLATE_ID == r["TEMPLATE_ID"])
            .where(recon_template_version.c.VERSION == r["TEMPLATE_VERSION"])
        ).first()
        if version_row is None:
            continue
        templates.append({"id": int(r["ID"]), "config": _parse_config(version_row[0])})
    detected = detect_template(storage_path, templates)
    if detected is not None:
        return "MATCHED", "HEADER", int(detected["id"]), []
    return "UNMATCHED", None, None, []


def _collect_uploads(
    ctx: Ctx, engine: Engine, run_id: int, files: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Tải các file lên RECON_FILE (mỗi lần một transaction riêng).

    Dùng chung cho add_files và replace_files. Trả về (pending, skipped,
    warnings); pending là các file chờ ghi dòng RECON_BATCH_RUN_FILE.
    """
    with engine.connect() as conn:
        existing_names = set(
            conn.execute(
                select(recon_batch_run_file.c.ORIGINAL_NAME).where(recon_batch_run_file.c.BATCH_RUN_ID == run_id)
            )
            .scalars()
            .all()
        )
        seen_sha: set[str] = set(
            conn.execute(
                select(recon_file.c.SHA256)
                .select_from(recon_batch_run_file.join(recon_file, recon_batch_run_file.c.FILE_ID == recon_file.c.ID))
                .where(recon_batch_run_file.c.BATCH_RUN_ID == run_id)
            )
            .scalars()
            .all()
        )
        current_count = len(existing_names)

    pending: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def _collect(
        display_name: str, match_name: str, uploaded: dict[str, Any], from_zip: str | None
    ) -> dict[str, Any] | None:
        if display_name in existing_names:
            skipped.append(
                {
                    "filename": display_name,
                    "reason": "BATCH_FILE_DUPLICATE",
                    "message": f"File '{display_name}' đã tồn tại trong lần chạy này.",
                }
            )
            return None
        if uploaded["sha256"] in seen_sha:
            warnings.append(
                {
                    "code": "BATCH_FILE_DUPLICATE",
                    "message": f"File '{display_name}' trùng nội dung với một file đã tải trước đó.",
                }
            )
        seen_sha.add(uploaded["sha256"])
        existing_names.add(display_name)
        entry = {
            "display_name": display_name,
            "match_name": match_name,
            "uploaded": uploaded,
            "from_zip_file_id": None,
            "from_zip": from_zip,
        }
        pending.append(entry)
        return entry

    for item in files:
        filename = item["filename"]
        content = item["content"]
        ext = Path(filename).suffix.lower()
        if ext not in ACCEPTED_EXTS:
            raise ServiceError(
                ErrorCode.FILE_TYPE_NOT_ALLOWED,
                f"Phần mở rộng '{ext}' không được hỗ trợ. Chỉ chấp nhận .xlsx, .xls, .csv, .zip.",
            )
        if ext == ".zip":
            zip_record = _upload_single(ctx, filename, content, engine)
            entries, zip_skipped = _extract_zip_entries(filename, content)
            skipped.extend(zip_skipped)
            for entry_name, entry_content in entries:
                display_name = f"{filename}/{entry_name}"
                uploaded = _upload_single(ctx, entry_name, entry_content, engine)
                entry = _collect(display_name, entry_name, uploaded, filename)
                if entry is not None:
                    entry["from_zip_file_id"] = int(zip_record["id"])
            continue
        uploaded = _upload_single(ctx, filename, content, engine)
        _collect(filename, filename, uploaded, None)

    if current_count + len(pending) > MAX_FILES_PER_RUN:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Lần chạy bộ chỉ nhận tối đa {MAX_FILES_PER_RUN} file.",
        )
    return pending, skipped, warnings


@service
@requires_menu("batch_run")
def add_files(ctx: Ctx, run_id: int, files: list[dict[str, Any]]) -> dict[str, Any]:
    """Tải file vào lần chạy bộ DRAFT và tự động ghép với mục.

    files: [{filename, content: bytes}]. .zip được giải nén (giới hạn theo
    spec 10 §10), mỗi file bên trong ghép riêng. File trùng tên hoặc vượt
    giới hạn được bỏ qua và báo trong skipped.

    Hai giai đoạn: (1) tải từng file lên RECON_FILE, mỗi lần tải dùng
    transaction riêng của nó, vì SQLite khóa DB khi hai transaction ghi
    lồng nhau; (2) một transaction duy nhất ghi các dòng
    RECON_BATCH_RUN_FILE kèm ghép. File đã tải ở giai đoạn 1 mà giai đoạn
    2 lỗi thì thành dòng RECON_FILE mồ côi (vô hại, như lần tải bị bỏ dở).
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        run = _get_run(conn, run_id)
        _check_run_editor(ctx, run, engine)
        _require_draft(run)
    pending, skipped, warnings = _collect_uploads(ctx, engine, run_id, files)

    # Giai đoạn 2: ghi RECON_BATCH_RUN_FILE + ghép, một transaction.
    added: list[dict[str, Any]] = []
    with engine.begin() as conn:
        run = _get_run(conn, run_id)
        _require_draft(run)
        for entry in pending:
            uploaded = entry["uploaded"]
            state, by, item_id, candidates = _match_item(conn, run_id, entry["match_name"], uploaded["storage_path"])
            file_id = conn.execute(
                insert(recon_batch_run_file).values(
                    BATCH_RUN_ID=run_id,
                    BATCH_RUN_ITEM_ID=item_id,
                    FILE_ID=int(uploaded["id"]),
                    FROM_ZIP_FILE_ID=entry["from_zip_file_id"],
                    ORIGINAL_NAME=entry["display_name"],
                    NORMALIZED_NAME=normalize_name(entry["match_name"]),
                    MATCH_STATE=state,
                    MATCH_BY=by,
                    CANDIDATE_ITEM_IDS=json.dumps(candidates, ensure_ascii=False),
                    CREATED_BY=ctx.username,
                    CREATED_AT=_now(),
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=_now(),
                )
            ).lastrowid
            added.append(
                {
                    "id": int(file_id),
                    "batch_run_id": run_id,
                    "batch_run_item_id": item_id,
                    "file_id": int(uploaded["id"]),
                    "original_name": entry["display_name"],
                    "match_state": state,
                    "match_by": by,
                    "candidate_item_ids": candidates,
                    "from_zip": entry["from_zip"],
                }
            )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN",
            entity_id=run_id,
            action="ADD_BATCH_RUN_FILES",
            actor=ctx.username,
            new_data={"added": len(added), "skipped": len(skipped)},
            now=_now(),
        )
    return {"added": added, "skipped": skipped, "warnings": warnings}


@service
@requires_menu("batch_run")
def assign_file(ctx: Ctx, file_id: int, item_id: int | None) -> dict[str, Any]:
    """Gán tay file vào mục (MATCH_BY='MANUAL') hoặc gỡ gán (item_id None)."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = conn.execute(select(recon_batch_run_file).where(recon_batch_run_file.c.ID == file_id)).mappings().first()
        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy file chạy bộ với id {file_id}.")
        file_rec = dict(row)
        run = _get_run(conn, int(file_rec["BATCH_RUN_ID"]))
        _check_run_editor(ctx, run, engine)
        _require_draft(run)
        if item_id is not None:
            item = conn.execute(
                select(recon_batch_run_item)
                .where(recon_batch_run_item.c.ID == item_id)
                .where(recon_batch_run_item.c.BATCH_RUN_ID == int(file_rec["BATCH_RUN_ID"]))
            ).first()
            if item is None:
                raise ServiceError(
                    ErrorCode.BATCH_NOT_FOUND,
                    "Mục chạy bộ không thuộc lần chạy này.",
                )
            new_state, new_by = "MATCHED", "MANUAL"
        else:
            new_state, new_by = "UNMATCHED", None
        conn.execute(
            update(recon_batch_run_file)
            .where(recon_batch_run_file.c.ID == file_id)
            .values(
                BATCH_RUN_ITEM_ID=item_id,
                MATCH_STATE=new_state,
                MATCH_BY=new_by,
                CANDIDATE_ITEM_IDS="[]",
            )
        )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN_FILE",
            entity_id=file_id,
            action="ASSIGN_BATCH_RUN_FILE",
            actor=ctx.username,
            new_data={"item_id": item_id},
            now=_now(),
        )
        updated = (
            conn.execute(select(recon_batch_run_file).where(recon_batch_run_file.c.ID == file_id)).mappings().first()
        )
        assert updated is not None
        return _run_file_dict(dict(updated))


@service
@requires_menu("batch_run")
def ignore_file(ctx: Ctx, file_id: int) -> dict[str, Any]:
    """Bỏ qua file đã tải (không đưa vào chạy)."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = conn.execute(select(recon_batch_run_file).where(recon_batch_run_file.c.ID == file_id)).mappings().first()
        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy file chạy bộ với id {file_id}.")
        file_rec = dict(row)
        run = _get_run(conn, int(file_rec["BATCH_RUN_ID"]))
        _check_run_editor(ctx, run, engine)
        _require_draft(run)
        conn.execute(
            update(recon_batch_run_file)
            .where(recon_batch_run_file.c.ID == file_id)
            .values(MATCH_STATE="IGNORED", UPDATED_BY=ctx.username, UPDATED_AT=_now())
        )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN_FILE",
            entity_id=file_id,
            action="IGNORE_BATCH_RUN_FILE",
            actor=ctx.username,
            new_data={},
            now=_now(),
        )
        updated = (
            conn.execute(select(recon_batch_run_file).where(recon_batch_run_file.c.ID == file_id)).mappings().first()
        )
        assert updated is not None
        return _run_file_dict(dict(updated))


@service
@requires_menu("batch_run")
def skip_item(ctx: Ctx, item_id: int, skipped: bool) -> dict[str, Any]:
    """Bỏ qua mục trong lần chạy này (USER_SKIP) hoặc bỏ chế độ bỏ qua."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        item = _get_run_item(conn, item_id)
        run = _get_run(conn, int(item["BATCH_RUN_ID"]))
        _check_run_editor(ctx, run, engine)
        _require_draft(run)
        if skipped:
            values = {
                "STATUS": "SKIPPED",
                "SKIP_REASON": "USER_SKIP",
                "SKIPPED_BY": ctx.username,
                "UPDATED_BY": ctx.username,
                "UPDATED_AT": _now(),
            }
        else:
            values = {
                "STATUS": "PENDING",
                "SKIP_REASON": None,
                "SKIPPED_BY": None,
                "UPDATED_BY": ctx.username,
                "UPDATED_AT": _now(),
            }
        conn.execute(update(recon_batch_run_item).where(recon_batch_run_item.c.ID == item_id).values(**values))
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN_ITEM",
            entity_id=item_id,
            action="SKIP_BATCH_RUN_ITEM",
            actor=ctx.username,
            new_data={"skipped": skipped},
            now=_now(),
        )
        updated = (
            conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.ID == item_id)).mappings().first()
        )
        assert updated is not None
        return _run_item_dict(dict(updated), [])


@service
@requires_menu("batch_run")
def set_param_override(ctx: Ctx, item_id: int, param_name: str, value: Any) -> dict[str, Any]:
    """Đặt/gỡ tham số ghi đè của lần chạy và giải lại tham số với kỳ."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        item = _get_run_item(conn, item_id)
        run = _get_run(conn, int(item["BATCH_RUN_ID"]))
        _check_run_editor(ctx, run, engine)
        _require_draft(run)
        version_row = conn.execute(
            select(recon_template_version.c.CONFIG_JSON)
            .where(recon_template_version.c.TEMPLATE_ID == item["TEMPLATE_ID"])
            .where(recon_template_version.c.VERSION == item["TEMPLATE_VERSION"])
        ).first()
        if version_row is None:
            raise ServiceError(
                ErrorCode.BATCH_TEMPLATE_NOT_ACTIVE,
                "Không tìm thấy version template của mục chạy bộ.",
            )
        cfg = TemplateConfig.model_validate(_parse_config(version_row[0]))
        def_item = (
            conn.execute(select(recon_batch_def_item).where(recon_batch_def_item.c.ID == item["BATCH_DEF_ITEM_ID"]))
            .mappings()
            .first()
        )
        def_override = _parse_json(def_item["PARAMS_OVERRIDE_JSON"], {}) if def_item else {}
        run_override = _parse_json(item["PARAMS_RUN_OVERRIDE_JSON"], {})
        if value is None:
            run_override.pop(param_name, None)
        else:
            run_override[param_name] = value
        resolved = resolve_params(cfg.db_source.params, def_override, run_override, run["PERIOD"])
        conn.execute(
            update(recon_batch_run_item)
            .where(recon_batch_run_item.c.ID == item_id)
            .values(
                PARAMS_RUN_OVERRIDE_JSON=json.dumps(run_override, ensure_ascii=False),
                PARAMS_RESOLVED_JSON=json.dumps(_serialize_params(resolved), ensure_ascii=False),
                UPDATED_BY=ctx.username,
                UPDATED_AT=_now(),
            )
        )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN_ITEM",
            entity_id=item_id,
            action="SET_BATCH_RUN_PARAM",
            actor=ctx.username,
            new_data={"param": param_name},
            now=_now(),
        )
        updated = (
            conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.ID == item_id)).mappings().first()
        )
        assert updated is not None
        return _run_item_dict(dict(updated), [])


# ─── Bước 6: precheck, start, đồng bộ trạng thái ──────────────────────────

_TERMINAL_ITEM_STATUSES = ("DONE", "FAILED", "SKIPPED", "NOT_RUN")


def sync_batch_status(engine: Engine, batch_run_id: int) -> dict[str, Any]:
    """Đồng bộ trạng thái mục từ run con và kết thúc lần chạy bộ.

    Mục QUEUED/RUNNING có CURRENT_RUN_ID sẽ theo trạng thái run con
    (DONE/FAILED). Khi mọi mục đã ở trạng thái cuối và batch run đang
    RUNNING: DONE nếu mọi mục DONE/SKIPPED (không có NOT_RUN bắt buộc),
    ngược lại PARTIAL. Dùng sau khi worker xong một run con, sau start
    và sau chạy lại (bước 7).
    """
    with engine.begin() as conn:
        run = _get_run(conn, batch_run_id)
        items = (
            conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.BATCH_RUN_ID == batch_run_id))
            .mappings()
            .all()
        )
        for item in items:
            if item["STATUS"] in ("QUEUED", "RUNNING") and item["CURRENT_RUN_ID"]:
                child = conn.execute(
                    select(recon_run.c.STATUS).where(recon_run.c.ID == int(item["CURRENT_RUN_ID"]))
                ).first()
                if child is not None and child[0] in ("DONE", "FAILED"):
                    conn.execute(
                        update(recon_batch_run_item)
                        .where(recon_batch_run_item.c.ID == item["ID"])
                        .values(STATUS=child[0], UPDATED_BY="system", UPDATED_AT=_now())
                    )
                elif child is not None and child[0] == "CANCELLED":
                    conn.execute(
                        update(recon_batch_run_item)
                        .where(recon_batch_run_item.c.ID == item["ID"])
                        .values(STATUS="NOT_RUN", UPDATED_BY="system", UPDATED_AT=_now())
                    )
        items = (
            conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.BATCH_RUN_ID == batch_run_id))
            .mappings()
            .all()
        )
        counts = {"DONE": 0, "FAILED": 0, "SKIPPED": 0, "NOT_RUN": 0}
        has_failed = False
        has_required_not_run = False
        all_terminal = True
        for item in items:
            status = str(item["STATUS"])
            if status in counts:
                counts[status] += 1
            if status == "FAILED":
                has_failed = True
            if status == "NOT_RUN" and item["IS_REQUIRED"] == "Y":
                has_required_not_run = True
            if status not in _TERMINAL_ITEM_STATUSES:
                all_terminal = False
        values: dict[str, Any] = {
            "CNT_DONE": counts["DONE"],
            "CNT_FAILED": counts["FAILED"],
            "CNT_SKIPPED": counts["SKIPPED"],
            "CNT_NOT_RUN": counts["NOT_RUN"],
            "UPDATED_BY": "system",
            "UPDATED_AT": _now(),
        }
        new_status = str(run["STATUS"])
        if run["STATUS"] == "RUNNING" and all_terminal:
            new_status = "PARTIAL" if (has_failed or has_required_not_run) else "DONE"
            values["STATUS"] = new_status
            values["FINISHED_AT"] = _now()
        conn.execute(update(recon_batch_run).where(recon_batch_run.c.ID == batch_run_id).values(**values))
        return {
            "id": batch_run_id,
            "status": new_status,
            "cnt_done": counts["DONE"],
            "cnt_failed": counts["FAILED"],
            "cnt_skipped": counts["SKIPPED"],
            "cnt_not_run": counts["NOT_RUN"],
        }


def _check_data_source_cached(ds_id: int, cache: dict[int, tuple[bool, str]], lock: threading.Lock) -> tuple[bool, str]:
    """Kiểm tra kết nối Data Source, cache kết quả theo DS trong lần precheck."""
    with lock:
        if ds_id in cache:
            return cache[ds_id]
    try:
        conn = open_source_connection(ds_id)
        try:
            conn.close()
        except Exception:
            pass
        result: tuple[bool, str] = (True, "")
    except ServiceError as exc:
        result = (False, exc.message)
    except Exception as exc:  # noqa: BLE001 - mọi lỗi kết nối đều là ERROR precheck
        result = (False, str(exc))
    with lock:
        cache[ds_id] = result
    return result


def _precheck_one_item(
    item: dict[str, Any],
    snapshot: dict[str, Any],
    ds_cache: dict[int, tuple[bool, str]],
    ds_lock: threading.Lock,
) -> dict[str, Any]:
    """Kiểm tra một mục: template, tham số, file, control total, DS.

    Chạy trong thread pool; chỉ đọc file và mở kết nối DS, không ghi DB.
    """
    import polars as pl

    checks: list[dict[str, Any]] = []
    cfg: TemplateConfig = snapshot["config"]
    period: str = snapshot["period"]
    rows_read = 0
    rows_valid = 0
    rows_invalid = 0
    rows_out_of_range = 0
    ct_summary: dict[str, Any] = {"matched": True, "per_file": []}

    # 1. Template còn Active, lấy version Active.
    if not snapshot["template_active"] or snapshot["version_row"] is None:
        checks.append(
            {
                "key": "template",
                "level": "error",
                "message": "Template không còn hoạt động hoặc không có version Active.",
            }
        )
    else:
        checks.append({"key": "template", "level": "ok", "message": "Template đang hoạt động."})

    # 2. Tham số hợp lệ (tính lại với kỳ).
    try:
        resolve_params(
            cfg.db_source.params,
            snapshot["def_override"],
            snapshot["run_override"],
            period,
        )
        checks.append({"key": "params", "level": "ok", "message": "Tham số hợp lệ."})
    except ServiceError as exc:
        checks.append({"key": "params", "level": "error", "message": exc.message})

    # 3. Đọc file + gộp (header, cột bắt buộc) và control total từng file.
    merged = None
    try:
        merged = merge_excel_files(snapshot["files"], cfg)
        rows_read = sum(m.rows_read for m in merged)
        rows_valid = sum(m.rows_valid for m in merged)
        rows_invalid = sum(m.rows_invalid for m in merged)
        checks.append(
            {"key": "files", "level": "ok", "message": f"Đọc được {len(merged)} file, {rows_valid} dòng hợp lệ."}
        )
    except ServiceError as exc:
        checks.append({"key": "files", "level": "error", "message": exc.message})
    except Exception as exc:  # noqa: BLE001 - lỗi đọc file là ERROR precheck
        checks.append({"key": "files", "level": "error", "message": f"Không đọc được file: {exc}"})

    if merged is not None:
        # 4. Control total từng file.
        per_file = []
        for m in merged:
            ok = m.control_total.is_matched if m.control_total is not None else None
            per_file.append(
                {
                    "name": m.name,
                    "file_total": str(m.control_total.file_total)
                    if m.control_total and m.control_total.file_total is not None
                    else None,
                    "calc_total": str(m.control_total.calc_total) if m.control_total else None,
                    "matched": ok,
                }
            )
        ct_total = sum_control_totals(merged)
        ct_summary = {
            "matched": bool(ct_total.is_matched) if ct_total else True,
            "file_total": str(ct_total.file_total) if ct_total and ct_total.file_total is not None else None,
            "calc_total": str(ct_total.calc_total) if ct_total else None,
            "per_file": per_file,
        }
        if ct_total is not None and not ct_total.is_matched:
            bad = [str(p["name"]) for p in per_file if p["matched"] is False]
            checks.append(
                {
                    "key": "control_total",
                    "level": "warn",
                    "message": f"Control total lệch ở file: {', '.join(bad)}.",
                }
            )
        else:
            checks.append({"key": "control_total", "level": "ok", "message": "Control total khớp."})

        # 5. Số dòng ngoài kỳ.
        resolved = _parse_json(item["PARAMS_RESOLVED_JSON"], {})
        try:
            p_from = datetime.fromisoformat(str(resolved.get("p_from"))) if resolved.get("p_from") else None
            p_to = datetime.fromisoformat(str(resolved.get("p_to"))) if resolved.get("p_to") else None
        except ValueError:
            p_from = p_to = None
        if cfg.time_filter is not None and p_from is not None and p_to is not None:
            valid_parts = [m.valid_df for m in merged if not m.valid_df.is_empty()]
            if valid_parts:
                merged_valid = pl.concat(valid_parts, how="diagonal")
                tf_res = apply_time_filter(merged_valid, cfg.time_filter, p_from, p_to)
                rows_out_of_range = int(tf_res.out_of_range_count)
        if rows_out_of_range > 0:
            checks.append(
                {
                    "key": "out_of_range",
                    "level": "warn",
                    "message": f"Có {rows_out_of_range} dòng ngoài kỳ.",
                }
            )
        else:
            checks.append({"key": "out_of_range", "level": "ok", "message": "Không có dòng ngoài kỳ."})

        # 6. Số dòng không hợp lệ.
        if rows_invalid > 0:
            checks.append({"key": "invalid_rows", "level": "warn", "message": f"Có {rows_invalid} dòng không hợp lệ."})
        else:
            checks.append({"key": "invalid_rows", "level": "ok", "message": "Không có dòng không hợp lệ."})

    # 7. Kết nối Data Source (cache theo DS).
    ds_ok, ds_msg = _check_data_source_cached(int(item["DATA_SOURCE_ID"]), ds_cache, ds_lock)
    if ds_ok:
        checks.append({"key": "data_source", "level": "ok", "message": "Kết nối Data Source thành công."})
    else:
        checks.append({"key": "data_source", "level": "error", "message": ds_msg or "Không kết nối được Data Source."})

    status = "READY"
    if any(c["level"] == "error" for c in checks):
        status = "ERROR"
    elif any(c["level"] == "warn" for c in checks):
        status = "WARN"
    precheck_json = {
        "checks": checks,
        "rows_read": rows_read,
        "rows_valid": rows_valid,
        "rows_invalid": rows_invalid,
        "rows_out_of_range": rows_out_of_range,
        "control_total": ct_summary,
    }
    return {"item_id": int(item["ID"]), "status": status, "precheck": precheck_json}


@service
@requires_menu("batch_run")
def precheck(ctx: Ctx, run_id: int, item_ids: list[int] | None = None) -> dict[str, Any]:
    """Kiểm tra trước cho các mục có file của lần chạy bộ DRAFT (spec 10 §5.4).

    Chạy song song có giới hạn (tối đa 4 luồng) cho các mục; không ghi dữ
    liệu tạm, không lưu kết quả. Ghi PRECHECK_JSON + STATUS (READY/WARN/
    ERROR) cho từng mục đã kiểm.
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        run = _get_run(conn, run_id)
        _check_run_editor(ctx, run, engine)
        _require_draft(run)
    return _run_precheck(engine, ctx, run, item_ids)


def _run_precheck(engine: Engine, ctx: Ctx, run: dict[str, Any], item_ids: list[int] | None = None) -> dict[str, Any]:
    """Lõi kiểm tra trước (dùng chung cho precheck và replace_files).

    Người gọi đã kiểm quyền; không yêu cầu DRAFT (replace_files chạy trên
    batch DONE/PARTIAL).
    """
    run_id = int(run["ID"])
    with engine.connect() as conn:
        item_rows = (
            conn.execute(
                select(recon_batch_run_item)
                .where(recon_batch_run_item.c.BATCH_RUN_ID == run_id)
                .where(recon_batch_run_item.c.STATUS.in_(["PENDING", "READY", "WARN", "ERROR"]))
                .order_by(recon_batch_run_item.c.PRIORITY, recon_batch_run_item.c.ID)
            )
            .mappings()
            .all()
        )
        if item_ids is not None:
            wanted = set(item_ids)
            item_rows = [r for r in item_rows if int(r["ID"]) in wanted]

        snapshots: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for item in item_rows:
            file_rows = (
                conn.execute(
                    select(recon_batch_run_file, recon_file.c.STORAGE_PATH, recon_file.c.ORIGINAL_NAME)
                    .select_from(
                        recon_batch_run_file.join(recon_file, recon_batch_run_file.c.FILE_ID == recon_file.c.ID)
                    )
                    .where(recon_batch_run_file.c.BATCH_RUN_ITEM_ID == item["ID"])
                    .where(recon_batch_run_file.c.MATCH_STATE == "MATCHED")
                    .order_by(recon_batch_run_file.c.ID)
                )
                .mappings()
                .all()
            )
            if not file_rows:
                continue
            tmpl_row = conn.execute(
                select(recon_template.c.STATUS).where(recon_template.c.ID == item["TEMPLATE_ID"])
            ).first()
            version_row = (
                conn.execute(
                    select(recon_template_version)
                    .where(recon_template_version.c.TEMPLATE_ID == item["TEMPLATE_ID"])
                    .where(recon_template_version.c.STATUS == "ACTIVE")
                    .order_by(recon_template_version.c.VERSION.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            cfg = None
            if version_row is not None:
                cfg = TemplateConfig.model_validate(_parse_config(version_row["CONFIG_JSON"]))
            def_item = (
                conn.execute(select(recon_batch_def_item).where(recon_batch_def_item.c.ID == item["BATCH_DEF_ITEM_ID"]))
                .mappings()
                .first()
            )
            snapshots.append(
                (
                    dict(item),
                    {
                        "config": cfg,
                        "template_active": tmpl_row is not None and tmpl_row[0] == "ACTIVE",
                        "version_row": dict(version_row) if version_row is not None else None,
                        "period": run["PERIOD"],
                        "def_override": _parse_json(def_item["PARAMS_OVERRIDE_JSON"], {}) if def_item else {},
                        "run_override": _parse_json(item["PARAMS_RUN_OVERRIDE_JSON"], {}),
                        "files": [(Path(str(f["STORAGE_PATH"])), str(f["ORIGINAL_NAME"])) for f in file_rows],
                    },
                )
            )

    ds_cache: dict[int, tuple[bool, str]] = {}
    ds_lock = threading.Lock()
    results: list[dict[str, Any]] = []
    checked = [snap_item for snap_item, snap in snapshots if snap["config"] is not None]
    # Mục không còn config (template bị xóa version) vẫn cần báo ERROR.
    for snap_item, snap in snapshots:
        if snap["config"] is None:
            results.append(
                {
                    "item_id": int(snap_item["ID"]),
                    "status": "ERROR",
                    "precheck": {
                        "checks": [
                            {
                                "key": "template",
                                "level": "error",
                                "message": "Template không còn version Active.",
                            }
                        ],
                        "rows_read": 0,
                        "rows_valid": 0,
                        "rows_invalid": 0,
                        "rows_out_of_range": 0,
                        "control_total": {"matched": True, "per_file": []},
                    },
                }
            )
    if checked:
        max_workers = min(4, len(checked))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(
                    _precheck_one_item,
                    snap_item,
                    snap,
                    ds_cache,
                    ds_lock,
                )
                for snap_item, snap in snapshots
                if snap["config"] is not None
            ]
            for fut in futures:
                results.append(fut.result())

    with engine.begin() as conn:
        for res in results:
            conn.execute(
                update(recon_batch_run_item)
                .where(recon_batch_run_item.c.ID == res["item_id"])
                .values(
                    STATUS=res["status"],
                    PRECHECK_JSON=json.dumps(res["precheck"], ensure_ascii=False),
                    PRECHECK_AT=_now(),
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=_now(),
                )
            )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN",
            entity_id=run_id,
            action="PRECHECK_BATCH_RUN",
            actor=ctx.username,
            new_data={"items": len(results)},
            now=_now(),
        )
        run_row = _get_run(conn, run_id)
        items_out = []
        for res in results:
            row = (
                conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.ID == res["item_id"]))
                .mappings()
                .first()
            )
            assert row is not None
            items_out.append(_run_item_dict(dict(row), []))
    out = _run_dict(run_row)
    out["items"] = items_out
    return out


def _create_child_run(
    conn: Connection, ctx: Ctx, run: dict[str, Any], item: dict[str, Any], now: datetime
) -> int | None:
    """Tạo run con QUEUED cho một mục (version Active lúc chạy, tham số từ
    PARAMS_RESOLVED_JSON). Trả về id run con, hoặc None khi template không
    còn version Active (người gọi đánh dấu NOT_RUN)."""
    file_rows = (
        conn.execute(
            select(recon_batch_run_file)
            .where(recon_batch_run_file.c.BATCH_RUN_ITEM_ID == item["ID"])
            .where(recon_batch_run_file.c.MATCH_STATE == "MATCHED")
            .order_by(recon_batch_run_file.c.ID)
        )
        .mappings()
        .all()
    )
    if not file_rows:
        return None
    version_row = (
        conn.execute(
            select(recon_template_version)
            .where(recon_template_version.c.TEMPLATE_ID == item["TEMPLATE_ID"])
            .where(recon_template_version.c.STATUS == "ACTIVE")
            .order_by(recon_template_version.c.VERSION.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if version_row is None:
        return None
    cfg = TemplateConfig.model_validate(_parse_config(version_row["CONFIG_JSON"]))
    resolved = _parse_json(item["PARAMS_RESOLVED_JSON"], {})
    p_from = _parse_dt(resolved.get("p_from")) or run["PERIOD_FROM"]
    p_to = _parse_dt(resolved.get("p_to")) or run["PERIOD_TO"]
    child_id = conn.execute(
        insert(recon_run)
        .values(
            TEMPLATE_ID=int(item["TEMPLATE_ID"]),
            TEMPLATE_VERSION=int(version_row["VERSION"]),
            PROFILE_CODE=str(item["PROFILE_CODE"]),
            PROFILE_OVERRIDE=None,
            FILE_ID=int(file_rows[0]["FILE_ID"]),
            EXCEL_LOAD_ID=None,
            SHEET_NAME=cfg.file.sheet,
            DATA_SOURCE_ID=int(item["DATA_SOURCE_ID"]),
            P_FROM=p_from,
            P_TO=p_to,
            PARAMS_JSON=resolved,
            APPLY_RANGE_EXCEL="Y",
            STATUS="QUEUED",
            PROGRESS_PCT=0,
            BATCH_RUN_ID=int(run["ID"]),
            BATCH_RUN_ITEM_ID=int(item["ID"]),
            CREATED_BY=ctx.username,
            CREATED_AT=now,
        )
        .returning(recon_run.c.ID)
    ).scalar()
    child_id = int(child_id) if child_id is not None else 0
    conn.execute(
        insert(recon_run_queue).values(
            RUN_ID=child_id,
            STATUS="READY",
            RETRY_COUNT=0,
            ENQUEUED_AT=now,
        )
    )
    conn.execute(
        update(recon_batch_run_item)
        .where(recon_batch_run_item.c.ID == item["ID"])
        .values(
            STATUS="QUEUED",
            TEMPLATE_VERSION=int(version_row["VERSION"]),
            CURRENT_RUN_ID=child_id,
            ATTEMPT_NO=int(item["ATTEMPT_NO"] or 0) + 1,
            ERROR_MSG=None,
            UPDATED_BY=ctx.username,
            UPDATED_AT=_now(),
        )
    )
    return child_id


@service
@requires_menu("batch_run")
def start(ctx: Ctx, run_id: int, include_warn: bool = True, confirm_prod: bool = False) -> dict[str, Any]:
    """Bắt đầu lần chạy bộ DRAFT: tạo run con QUEUED cho từng mục đủ điều
    kiện (spec 10 §5.5).

    Mục READY chạy; mục WARN chạy khi include_warn=True, ngược lại NOT_RUN;
    mục ERROR/PENDING (chưa precheck) → NOT_RUN; mục không có file: bắt
    buộc → NOT_RUN, không bắt buộc → SKIPPED/NO_FILE. Data Source PROD
    cần confirm_prod (xác nhận một lần cho cả lần chạy, Q4).
    """
    engine = get_recon_engine()
    with engine.begin() as conn:
        run = _get_run(conn, run_id)
        _check_run_editor(ctx, run, engine)
        _require_draft(run)
        items = (
            conn.execute(
                select(recon_batch_run_item)
                .where(recon_batch_run_item.c.BATCH_RUN_ID == run_id)
                .order_by(recon_batch_run_item.c.PRIORITY, recon_batch_run_item.c.ID)
            )
            .mappings()
            .all()
        )

        # PROD: liệt kê các Data Source PROD của mục sẽ chạy.
        prod_ds: list[str] = []
        for item in items:
            if str(item["STATUS"]) in ("READY", "WARN"):
                ds = (
                    conn.execute(select(recon_data_source).where(recon_data_source.c.ID == int(item["DATA_SOURCE_ID"])))
                    .mappings()
                    .first()
                )
                if ds is not None and ds["ENV"] == "PROD":
                    prod_ds.append(str(ds["NAME"]))
        prod_ds = sorted(set(prod_ds))
        if prod_ds and not confirm_prod:
            raise ServiceError(
                ErrorCode.PROD_CONFIRM_REQUIRED,
                "Lần chạy bộ dùng Data Source thuộc môi trường PROD ("
                + ", ".join(prod_ds)
                + "). Cần xác nhận trước khi chạy.",
                {"prod_data_sources": prod_ds},
            )

        now = _now()
        started = 0
        not_run = 0
        for item in items:
            status = str(item["STATUS"])
            if status == "SKIPPED":
                continue
            file_rows = (
                conn.execute(
                    select(recon_batch_run_file)
                    .where(recon_batch_run_file.c.BATCH_RUN_ITEM_ID == item["ID"])
                    .where(recon_batch_run_file.c.MATCH_STATE == "MATCHED")
                )
                .mappings()
                .all()
            )
            has_files = len(file_rows) > 0

            def _mark(
                item_id: int, new_status: str, skip_reason: str | None = None, error_msg: str | None = None
            ) -> None:
                conn.execute(
                    update(recon_batch_run_item)
                    .where(recon_batch_run_item.c.ID == item_id)
                    .values(
                        STATUS=new_status,
                        SKIP_REASON=skip_reason,
                        ERROR_MSG=error_msg,
                        UPDATED_BY=ctx.username,
                        UPDATED_AT=_now(),
                    )
                )

            if status in ("READY", "WARN"):
                if status == "WARN" and not include_warn:
                    _mark(int(item["ID"]), "NOT_RUN")
                    not_run += 1
                    continue
                if not has_files:
                    if item["IS_REQUIRED"] == "Y":
                        _mark(int(item["ID"]), "NOT_RUN")
                        not_run += 1
                    else:
                        _mark(int(item["ID"]), "SKIPPED", skip_reason="NO_FILE")
                    continue
                child_id = _create_child_run(conn, ctx, run, dict(item), now)
                if child_id is None:
                    _mark(
                        int(item["ID"]),
                        "NOT_RUN",
                        error_msg="Template không còn version Active lúc chạy.",
                    )
                    not_run += 1
                    continue
                started += 1
            elif status == "PENDING":
                if not has_files:
                    if item["IS_REQUIRED"] == "Y":
                        _mark(int(item["ID"]), "NOT_RUN")
                        not_run += 1
                    else:
                        _mark(int(item["ID"]), "SKIPPED", skip_reason="NO_FILE")
                else:
                    _mark(int(item["ID"]), "NOT_RUN")
                    not_run += 1
            elif status == "ERROR":
                _mark(int(item["ID"]), "NOT_RUN")
                not_run += 1

        conn.execute(
            update(recon_batch_run)
            .where(recon_batch_run.c.ID == run_id)
            .values(
                STATUS="RUNNING",
                STARTED_AT=now,
                PROD_CONFIRMED_BY=ctx.username if (prod_ds and confirm_prod) else None,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
            )
        )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN",
            entity_id=run_id,
            action="START_BATCH_RUN",
            actor=ctx.username,
            new_data={"started": started, "not_run": not_run, "prod_data_sources": prod_ds},
            now=now,
        )

    sync_batch_status(engine, run_id)
    with engine.connect() as conn:
        run_row = _get_run(conn, run_id)
        out = _load_run_full(conn, run_row)
    out["started"] = started
    out["not_run"] = not_run
    out["prod_data_sources"] = prod_ds
    out["prod_confirmed_by"] = ctx.username if (prod_ds and confirm_prod) else None
    return out


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


# ─── Bước 7: chạy lại, thay file, hủy, ma trận, .zip ──────────────────────


@service
@requires_menu("batch_run")
def retry_failed(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Chạy lại các mục FAILED của lần chạy bộ (spec 10 §5.7).

    Mỗi mục FAILED tạo run con mới (cùng file, cùng tham số đã tính),
    cập nhật CURRENT_RUN_ID, tăng ATTEMPT_NO. Run cũ giữ nguyên trong
    lịch sử. Batch chuyển lại RUNNING.
    """
    engine = get_recon_engine()
    with engine.begin() as conn:
        run = _get_run(conn, run_id)
        _check_run_editor(ctx, run, engine)
        if run["STATUS"] in ("DRAFT", "CANCELLED"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ chạy lại khi lần chạy bộ đang chạy hoặc đã kết thúc (PARTIAL/DONE).",
            )
        items = (
            conn.execute(
                select(recon_batch_run_item)
                .where(recon_batch_run_item.c.BATCH_RUN_ID == run_id)
                .where(recon_batch_run_item.c.STATUS == "FAILED")
                .order_by(recon_batch_run_item.c.PRIORITY, recon_batch_run_item.c.ID)
            )
            .mappings()
            .all()
        )
        if not items:
            raise ServiceError(ErrorCode.BATCH_NOTHING_TO_RUN, "Không có mục nào FAILED để chạy lại.")
        now = _now()
        started = 0
        for item in items:
            child_id = _create_child_run(conn, ctx, run, dict(item), now)
            if child_id is None:
                conn.execute(
                    update(recon_batch_run_item)
                    .where(recon_batch_run_item.c.ID == item["ID"])
                    .values(
                        STATUS="NOT_RUN",
                        ERROR_MSG="Template không còn version Active lúc chạy lại.",
                        UPDATED_BY=ctx.username,
                        UPDATED_AT=_now(),
                    )
                )
                continue
            started += 1
        if started == 0:
            raise ServiceError(ErrorCode.BATCH_NOTHING_TO_RUN, "Không tạo được run con nào để chạy lại.")
        conn.execute(
            update(recon_batch_run)
            .where(recon_batch_run.c.ID == run_id)
            .values(STATUS="RUNNING", FINISHED_AT=None, UPDATED_BY=ctx.username, UPDATED_AT=now)
        )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN",
            entity_id=run_id,
            action="RETRY_FAILED_BATCH_RUN",
            actor=ctx.username,
            new_data={"started": started},
            now=now,
        )
    sync_batch_status(engine, run_id)
    with engine.connect() as conn:
        run_row = _get_run(conn, run_id)
        out = _load_run_full(conn, run_row)
    out["started"] = started
    return out


@service
@requires_menu("batch_run")
def rerun_item(ctx: Ctx, item_id: int) -> dict[str, Any]:
    """Chạy lại một mục (DONE/FAILED/NOT_RUN) với cùng file và tham số.

    Áp dụng cả khi mục đã DONE (sửa file sai xong chạy lại sau khi thay
    file). Batch DONE/PARTIAL chuyển lại RUNNING.
    """
    engine = get_recon_engine()
    with engine.begin() as conn:
        item = _get_run_item(conn, item_id)
        run = _get_run(conn, int(item["BATCH_RUN_ID"]))
        _check_run_editor(ctx, run, engine)
        if run["STATUS"] in ("DRAFT", "CANCELLED"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, "Lần chạy bộ chưa bắt đầu hoặc đã hủy, không thể chạy lại mục."
            )
        if str(item["STATUS"]) in ("QUEUED", "RUNNING"):
            raise ServiceError(ErrorCode.BATCH_RUN_BUSY, "Mục đang chạy, không thể chạy lại lúc này.")
        if str(item["STATUS"]) not in ("DONE", "FAILED", "NOT_RUN"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Mục ở trạng thái {item['STATUS']}, không thể chạy lại.",
            )
        now = _now()
        child_id = _create_child_run(conn, ctx, run, dict(item), now)
        if child_id is None:
            raise ServiceError(
                ErrorCode.BATCH_TEMPLATE_NOT_ACTIVE, "Template không còn version Active hoặc mục không còn file."
            )
        if run["STATUS"] in ("DONE", "PARTIAL"):
            conn.execute(
                update(recon_batch_run)
                .where(recon_batch_run.c.ID == int(item["BATCH_RUN_ID"]))
                .values(STATUS="RUNNING", FINISHED_AT=None, UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN_ITEM",
            entity_id=item_id,
            action="RERUN_BATCH_RUN_ITEM",
            actor=ctx.username,
            new_data={"child_run_id": child_id},
            now=now,
        )
        updated = (
            conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.ID == item_id)).mappings().first()
        )
        assert updated is not None
        return _run_item_dict(dict(updated), [])


@service
@requires_menu("batch_run")
def replace_files(ctx: Ctx, item_id: int, files: list[dict[str, Any]]) -> dict[str, Any]:
    """Thay file của một mục rồi precheck lại riêng mục đó (spec 10 §5.7).

    File cũ chuyển sang REPLACED (giữ lịch sử). File mới: khớp mẫu/header
    với đúng mục này thì MATCHED; khớp mục khác hoặc mơ hồ thì UNMATCHED;
    không khớp gì thì gán tay (MANUAL) cho mục này. Batch run không yêu
    cầu DRAFT, nhưng mục đang QUEUED/RUNNING thì chặn (BATCH_RUN_BUSY).
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        item = _get_run_item(conn, item_id)
        run = _get_run(conn, int(item["BATCH_RUN_ID"]))
        _check_run_editor(ctx, run, engine)
        if str(item["STATUS"]) in ("QUEUED", "RUNNING"):
            raise ServiceError(ErrorCode.BATCH_RUN_BUSY, "Mục đang chạy, không thể thay file lúc này.")
        if run["STATUS"] == "CANCELLED":
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Lần chạy bộ đã hủy, không thể thay file.")
    run_id = int(item["BATCH_RUN_ID"])
    pending, skipped, warnings = _collect_uploads(ctx, engine, run_id, files)
    if not pending:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Không có file mới nào được tải lên để thay thế.")

    with engine.begin() as conn:
        conn.execute(
            update(recon_batch_run_file)
            .where(recon_batch_run_file.c.BATCH_RUN_ITEM_ID == item_id)
            .where(recon_batch_run_file.c.MATCH_STATE == "MATCHED")
            .values(MATCH_STATE="REPLACED", UPDATED_BY=ctx.username, UPDATED_AT=_now())
        )
        added: list[dict[str, Any]] = []
        for entry in pending:
            uploaded = entry["uploaded"]
            state, by, matched_id, candidates = _match_item(conn, run_id, entry["match_name"], uploaded["storage_path"])
            if state == "MATCHED" and matched_id != item_id:
                state, by, matched_id, candidates = "UNMATCHED", None, None, []
            elif state != "MATCHED":
                if state == "AMBIGUOUS":
                    state, by, matched_id = "UNMATCHED", None, None
                else:
                    state, by, matched_id = "MATCHED", "MANUAL", int(item_id)
            file_id = conn.execute(
                insert(recon_batch_run_file).values(
                    BATCH_RUN_ID=run_id,
                    BATCH_RUN_ITEM_ID=matched_id,
                    FILE_ID=int(uploaded["id"]),
                    FROM_ZIP_FILE_ID=entry["from_zip_file_id"],
                    ORIGINAL_NAME=entry["display_name"],
                    NORMALIZED_NAME=normalize_name(entry["match_name"]),
                    MATCH_STATE=state,
                    MATCH_BY=by,
                    CANDIDATE_ITEM_IDS=json.dumps(candidates, ensure_ascii=False),
                    CREATED_BY=ctx.username,
                    CREATED_AT=_now(),
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=_now(),
                )
            ).lastrowid
            added.append(
                {
                    "id": int(file_id),
                    "batch_run_id": run_id,
                    "batch_run_item_id": matched_id,
                    "file_id": int(uploaded["id"]),
                    "original_name": entry["display_name"],
                    "match_state": state,
                    "match_by": by,
                    "candidate_item_ids": candidates,
                    "from_zip": entry["from_zip"],
                }
            )
        conn.execute(
            update(recon_batch_run_item)
            .where(recon_batch_run_item.c.ID == item_id)
            .values(
                STATUS="PENDING",
                PRECHECK_JSON=None,
                PRECHECK_AT=None,
                ERROR_MSG=None,
                UPDATED_BY=ctx.username,
                UPDATED_AT=_now(),
            )
        )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN_ITEM",
            entity_id=item_id,
            action="REPLACE_BATCH_RUN_FILES",
            actor=ctx.username,
            new_data={"added": len(added), "skipped": len(skipped)},
            now=_now(),
        )
    checked = _run_precheck(engine, ctx, run, [int(item_id)])
    item_out = checked["items"][0] if checked["items"] else None
    if item_out is None:
        with engine.connect() as conn:
            row = (
                conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.ID == item_id))
                .mappings()
                .first()
            )
            assert row is not None
            item_out = _run_item_dict(dict(row), [])
    item_out["added_files"] = added
    item_out["skipped_files"] = skipped
    item_out["warnings"] = warnings
    return item_out


@service
@requires_menu("batch_run")
def cancel(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Hủy lần chạy bộ DRAFT hoặc RUNNING (spec 10 §5.1).

    DRAFT: chuyển CANCELLED. RUNNING: chuyển CANCELLED; run con chưa chạy
    (QUEUED) bị hủy ngay (xóa hàng đợi, run CANCELLED, mục NOT_RUN); run
    con đang chạy tự dừng ở bước kiểm tra tiếp theo của executor.
    """
    engine = get_recon_engine()
    with engine.begin() as conn:
        run = _get_run(conn, run_id)
        _check_run_editor(ctx, run, engine)
        if run["STATUS"] not in ("DRAFT", "RUNNING"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ hủy được lần chạy bộ ở trạng thái DRAFT hoặc RUNNING.",
            )
        now = _now()
        if run["STATUS"] == "RUNNING":
            queued_items = (
                conn.execute(
                    select(recon_batch_run_item)
                    .where(recon_batch_run_item.c.BATCH_RUN_ID == run_id)
                    .where(recon_batch_run_item.c.STATUS == "QUEUED")
                )
                .mappings()
                .all()
            )
            for item in queued_items:
                child_id = item["CURRENT_RUN_ID"]
                if child_id is None:
                    continue
                child = conn.execute(select(recon_run.c.STATUS).where(recon_run.c.ID == int(child_id))).first()
                if child is not None and child[0] == "QUEUED":
                    conn.execute(delete(recon_run_queue).where(recon_run_queue.c.RUN_ID == int(child_id)))
                    conn.execute(
                        update(recon_run)
                        .where(recon_run.c.ID == int(child_id))
                        .values(STATUS="CANCELLED", STAGE="CANCELLED", FINISHED_AT=now)
                    )
                    conn.execute(
                        update(recon_batch_run_item)
                        .where(recon_batch_run_item.c.ID == item["ID"])
                        .values(STATUS="NOT_RUN", UPDATED_BY=ctx.username, UPDATED_AT=now)
                    )
        conn.execute(
            update(recon_batch_run)
            .where(recon_batch_run.c.ID == run_id)
            .values(STATUS="CANCELLED", FINISHED_AT=now, UPDATED_BY=ctx.username, UPDATED_AT=now)
        )
        write_audit_log(
            conn=conn,
            entity="BATCH_RUN",
            entity_id=run_id,
            action="CANCEL_BATCH_RUN",
            actor=ctx.username,
            new_data={},
            now=now,
        )
        run_row = _get_run(conn, run_id)
        return _load_run_full(conn, run_row)


def _compute_matrix(engine: Engine, run: dict[str, Any]) -> dict[str, Any]:
    """Ma trận kết quả lần chạy bộ (spec 10 mục 6).

    Số liệu lấy từ RECON_RUN_SUMMARY của CURRENT_RUN_ID, không tính lại.
    Tỷ lệ khớp so với lần chạy DONE gần nhất của cùng bộ ở kỳ trước.
    """
    run_id = int(run["ID"])
    with engine.connect() as conn:
        def_row = _get_def(conn, int(run["BATCH_DEF_ID"]))
        items = _load_items(conn, run_id)
        prev_run = (
            conn.execute(
                select(recon_batch_run)
                .where(recon_batch_run.c.BATCH_DEF_ID == int(run["BATCH_DEF_ID"]))
                .where(recon_batch_run.c.PERIOD < run["PERIOD"])
                .where(recon_batch_run.c.STATUS == "DONE")
                .order_by(recon_batch_run.c.PERIOD.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        prev_rates: dict[int, float] = {}
        if prev_run is not None:
            prev_items = (
                conn.execute(
                    select(recon_batch_run_item).where(recon_batch_run_item.c.BATCH_RUN_ID == int(prev_run["ID"]))
                )
                .mappings()
                .all()
            )
            for prev_item in prev_items:
                if prev_item["CURRENT_RUN_ID"] is None:
                    continue
                summ = (
                    conn.execute(
                        select(recon_run_summary).where(recon_run_summary.c.RUN_ID == int(prev_item["CURRENT_RUN_ID"]))
                    )
                    .mappings()
                    .first()
                )
                if summ is not None:
                    prev_rates[int(prev_item["TEMPLATE_ID"])] = _match_rate(summ)

        rows: list[dict[str, Any]] = []
        kpis = {
            "items_with_results": 0,
            "all_matched_items": 0,
            "mismatch_items": 0,
            "mismatch_total_diff": 0.0,
            "error_items": 0,
            "skipped_items": 0,
        }
        for item in items:
            tmpl = conn.execute(
                select(recon_template.c.CODE, recon_template.c.NAME).where(
                    recon_template.c.ID == int(item["template_id"])
                )
            ).first()
            summary = None
            child_run = None
            if item["current_run_id"] is not None:
                summary = (
                    conn.execute(
                        select(recon_run_summary).where(recon_run_summary.c.RUN_ID == int(item["current_run_id"]))
                    )
                    .mappings()
                    .first()
                )
                child_run = (
                    conn.execute(select(recon_run).where(recon_run.c.ID == int(item["current_run_id"])))
                    .mappings()
                    .first()
                )
            main_measure = None
            excel_total = None
            db_total = None
            diff_total = None
            if summary is not None:
                totals = _parse_json(summary["MEASURE_TOTALS_JSON"], {})
                main_measure = _main_measure(
                    conn, int(item["template_id"]), item["template_version"], item["profile_code"]
                )
                if main_measure and main_measure in totals:
                    excel_total = _to_float(totals[main_measure].get("excel"))
                    db_total = _to_float(totals[main_measure].get("db"))
                    diff_total = _to_float(totals[main_measure].get("diff"))
            match_rate = _match_rate(summary) if summary is not None else None
            prev_rate = prev_rates.get(int(item["template_id"]))
            delta = None
            if match_rate is not None and prev_rate is not None:
                delta = match_rate - prev_rate
            status = str(item["status"])
            if summary is not None:
                kpis["items_with_results"] += 1
                if (
                    int(summary["CNT_MISMATCH"] or 0) == 0
                    and int(summary["CNT_MISSING_IN_DB"] or 0) == 0
                    and int(summary["CNT_MISSING_IN_EXCEL"] or 0) == 0
                    and int(summary["CNT_INCONSISTENT"] or 0) == 0
                    and int(summary["CNT_DUPLICATE"] or 0) == 0
                ):
                    kpis["all_matched_items"] += 1
                else:
                    kpis["mismatch_items"] += 1
                    if diff_total is not None:
                        kpis["mismatch_total_diff"] += abs(diff_total)
            if status in ("FAILED", "ERROR", "NOT_RUN"):
                kpis["error_items"] += 1
            if status == "SKIPPED":
                kpis["skipped_items"] += 1
            rows.append(
                {
                    "item_id": int(item["id"]),
                    "template_id": int(item["template_id"]),
                    "template_code": str(tmpl[0]) if tmpl else "",
                    "template_name": str(tmpl[1]) if tmpl else "",
                    "file_count": len(item["files"]),
                    "status": status,
                    "skip_reason": item["skip_reason"],
                    "current_run_id": item["current_run_id"],
                    "attempt_no": int(item["attempt_no"]),
                    "main_measure": main_measure,
                    "excel_total": excel_total,
                    "db_total": db_total,
                    "diff_total": diff_total,
                    "cnt_matched": int(summary["CNT_MATCHED"]) if summary is not None else None,
                    "cnt_mismatch": int(summary["CNT_MISMATCH"]) if summary is not None else None,
                    "cnt_missing_in_db": int(summary["CNT_MISSING_IN_DB"]) if summary is not None else None,
                    "cnt_missing_in_excel": int(summary["CNT_MISSING_IN_EXCEL"]) if summary is not None else None,
                    "cnt_inconsistent": int(summary["CNT_INCONSISTENT"]) if summary is not None else None,
                    "cnt_duplicate": int(summary["CNT_DUPLICATE"]) if summary is not None else None,
                    "match_rate": match_rate,
                    "prev_match_rate": prev_rate,
                    "match_rate_delta": delta,
                    "checked_by": str(child_run["CHECKED_BY"]) if child_run and child_run["CHECKED_BY"] else None,
                    "checked_at": _iso(child_run["CHECKED_AT"]) if child_run else None,
                }
            )
    total_items = len(items)
    return {
        "run": _run_dict(run),
        "def_code": str(def_row["CODE"]),
        "def_name": str(def_row["NAME"]),
        "total_items": total_items,
        "kpis": kpis,
        "rows": rows,
    }


def _match_rate(summary: Any) -> float:
    total = (
        int(summary["CNT_MATCHED"] or 0)
        + int(summary["CNT_MISMATCH"] or 0)
        + int(summary["CNT_MISSING_IN_DB"] or 0)
        + int(summary["CNT_MISSING_IN_EXCEL"] or 0)
        + int(summary["CNT_INCONSISTENT"] or 0)
        + int(summary["CNT_DUPLICATE"] or 0)
    )
    if total == 0:
        return 0.0
    return int(summary["CNT_MATCHED"] or 0) / total


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _main_measure(conn: Connection, template_id: int, template_version: int | None, profile_code: str) -> str | None:
    if template_version is None:
        return None
    version_row = conn.execute(
        select(recon_template_version.c.CONFIG_JSON)
        .where(recon_template_version.c.TEMPLATE_ID == template_id)
        .where(recon_template_version.c.VERSION == template_version)
    ).first()
    if version_row is None:
        return None
    cfg = TemplateConfig.model_validate(_parse_config(version_row[0]))
    profile = next((p for p in cfg.profiles if p.code == profile_code), cfg.profiles[0] if cfg.profiles else None)
    if profile is None:
        return None
    return profile.main_measure or (profile.measures[0].name if profile.measures else None)


@service
@requires_menu("batch_run")
def matrix(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Ma trận kết quả lần chạy bộ (spec 10 mục 6)."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        run = check_owned(conn, recon_batch_run, "ID", run_id, ctx, engine=engine)
        return _compute_matrix(engine, dict(run))


def _zip_run_set_hash(items: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        sorted([[int(i["id"]), i["current_run_id"]] for i in items]),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _build_summary_xlsx(matrix_data: dict[str, Any], path: Path) -> None:
    """File tổng hợp 00_TONG_HOP: ma trận + sheet Tham số + sheet File."""
    import xlsxwriter

    wb = xlsxwriter.Workbook(str(path))
    header_fmt = wb.add_format({"bold": True})
    ws = wb.add_worksheet("Ma trận")
    headers = [
        "Mục",
        "Template",
        "Số file",
        "Trạng thái",
        "Tổng Excel",
        "Tổng DB",
        "Chênh lệch",
        "Khớp",
        "Lệch",
        "Thiếu DB",
        "Thiếu Excel",
        "Tỷ lệ khớp",
        "Kỳ trước",
        "Chênh lệch tỷ lệ",
    ]
    ws.write_row(0, 0, headers, header_fmt)
    for i, row in enumerate(matrix_data["rows"], start=1):
        ws.write_row(
            i,
            0,
            [
                row["template_code"],
                row["template_name"],
                row["file_count"],
                row["status"],
                row["excel_total"],
                row["db_total"],
                row["diff_total"],
                row["cnt_matched"],
                row["cnt_mismatch"],
                row["cnt_missing_in_db"],
                row["cnt_missing_in_excel"],
                row["match_rate"],
                row["prev_match_rate"],
                row["match_rate_delta"],
            ],
        )
    ws_params = wb.add_worksheet("Tham số")
    ws_params.write_row(0, 0, ["Mục", "Template", "Tham số", "Giá trị"], header_fmt)
    r = 1
    for row in matrix_data["rows"]:
        params = row.get("params_resolved") or {}
        for key, value in params.items():
            ws_params.write_row(r, 0, [row["template_code"], row["template_name"], key, str(value)])
            r += 1
    ws_files = wb.add_worksheet("File")
    ws_files.write_row(0, 0, ["Mục", "Template", "File", "Trạng thái ghép"], header_fmt)
    r = 1
    for row in matrix_data["rows"]:
        for f in row.get("files") or []:
            ws_files.write_row(
                r, 0, [row["template_code"], row["template_name"], f.get("original_name"), f.get("match_state")]
            )
            r += 1
    wb.close()


@service
@requires_menu("batch_run")
def build_zip(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Sinh file .zip kết quả lần chạy bộ (spec 10 mục 6).

    Gồm 00_TONG_HOP_<YYYYMM>.xlsx + file riêng từng mục có kết quả
    (giống hệt export của run). Cache theo (BATCH_RUN_ID, danh sách
    CURRENT_RUN_ID): chạy lại một mục thì cache bị vô hiệu.
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        run = check_owned(conn, recon_batch_run, "ID", run_id, ctx, engine=engine)
        run = dict(run)
    matrix_data = _compute_matrix(engine, run)
    with engine.connect() as conn:
        items = _load_items(conn, run_id)
    run_hash = _zip_run_set_hash(items)
    stored_path = run.get("ZIP_PATH")
    stored_hash = run.get("ZIP_RUN_SET_HASH")
    if stored_hash == run_hash and stored_path and Path(str(stored_path)).exists():
        return {
            "zip_path": str(stored_path),
            "file_name": Path(str(stored_path)).name,
            "cached": True,
        }

    def_row_code = matrix_data["def_code"]
    period_compact = str(run["PERIOD"]).replace("-", "")
    zip_name = f"{def_row_code}_{period_compact}_{run_id}.zip"
    batch_dir = Path(get_settings().RECON_STORAGE_DIR) / "batch" / str(run_id)
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / zip_name

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        summary_name = f"00_TONG_HOP_{period_compact}.xlsx"
        summary_path = tmp_path / summary_name
        # Ma trận cần kèm tham số đã tính + file đã ghép từng mục.
        for row in matrix_data["rows"]:
            item = next((i for i in items if int(i["id"]) == row["item_id"]), None)
            row["params_resolved"] = item["params_resolved"] if item else {}
            row["files"] = item["files"] if item else []
        _build_summary_xlsx(matrix_data, summary_path)
        parts: list[tuple[str, Path]] = [(summary_name, summary_path)]
        for row in matrix_data["rows"]:
            if row["current_run_id"] is None or row["status"] != "DONE":
                continue
            nn = f"{int(row['item_id']):02d}"
            part_name = f"{nn}_{row['template_code']}_{period_compact}.xlsx"
            part_path = tmp_path / part_name
            exp = export_run(ctx, int(row["current_run_id"]), output_path=part_path)
            if not exp.ok:
                continue
            parts.append((part_name, part_path))
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for arc_name, src in parts:
                zf.write(src, arc_name)

    with engine.begin() as conn:
        conn.execute(
            update(recon_batch_run)
            .where(recon_batch_run.c.ID == run_id)
            .values(ZIP_PATH=str(zip_path), ZIP_RUN_SET_HASH=run_hash, UPDATED_BY=ctx.username, UPDATED_AT=_now())
        )
    return {"zip_path": str(zip_path), "file_name": zip_name, "cached": False}
