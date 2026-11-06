"""Service chạy bộ — Bước 4 task 18 (tạo, tải file, ghép, tham số).

Các hàm bước 6/7 (precheck, start, retry, cancel, matrix, build_zip) ở
bước 6 và 7. Tạo lần chạy bộ (spec 10 mục 5.1), tải file lần chạy bộ
(mục 5.2), kiểm tra tham số (mục 5.3).
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

from app.core.audit import write_audit_log
from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_batch_def,
    recon_batch_def_item,
    recon_batch_run,
    recon_batch_run_file,
    recon_batch_run_item,
    recon_file,
    recon_template,
    recon_template_version,
)
from app.engine.mapping import detect_template
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
    items = [_run_item_dict(dict(r), files_by_item.get(r["ID"], []) if with_files else []) for r in item_rows]
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
    import hashlib

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

    # Giai đoạn 1: tải file lên RECON_FILE (transaction riêng từng file).
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
