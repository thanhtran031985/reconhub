"""Service Bộ đối soát — task 18, spec 10/10a.

CRUD RECON_BATCH_DEF + RECON_BATCH_DEF_ITEM. Tạo/sửa/archive bộ và
thêm/gỡ template: ADMIN + TEMPLATE_OWNER (spec 10 mục 7); đọc: mọi vai
trò có menu batch_def. Kích hoạt (DRAFT → ACTIVE) không có trong bảng
service spec 10 mục 8 nhưng spec 10a mục 1 yêu cầu điều kiện kích hoạt
nên service có thêm `activate_batch_def` (ghi decisions.md).
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Connection, func, select
from sqlalchemy.engine import RowMapping

from app.core.audit import write_audit_log
from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_batch_def,
    recon_batch_def_item,
    recon_batch_run_item,
    recon_template,
    recon_template_version,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import TemplateConfig
from app.services import service
from app.services.batch_formula import parse_period, resolve, resolve_params
from app.services.perm import requires_menu

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,59}$")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BatchDefCreate(BaseModel):
    """Payload tạo bộ đối soát (CODE không đổi sau tạo)."""

    code: str = Field(pattern=_CODE_RE)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    max_parallel_per_ds: int = Field(default=2, ge=1, le=4)


class BatchDefUpdate(BaseModel):
    """Payload sửa bộ đối soát (không đổi CODE)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    max_parallel_per_ds: int | None = Field(default=None, ge=1, le=4)


class BatchDefItemCreate(BaseModel):
    """Payload thêm template vào bộ."""

    template_id: int
    file_pattern: str = Field(min_length=1, max_length=400)
    multi_file: bool = False
    is_required: bool = True
    priority: int = Field(default=100)
    profile_code: str | None = Field(default=None, max_length=60)
    data_source_id: int | None = None
    params_override: dict[str, Any] | None = None


class BatchDefItemUpdate(BaseModel):
    """Payload sửa mục trong bộ."""

    file_pattern: str | None = Field(default=None, min_length=1, max_length=400)
    multi_file: bool | None = None
    is_required: bool | None = None
    priority: int | None = None
    profile_code: str | None = Field(default=None, max_length=60)
    data_source_id: int | None = None
    params_override: dict[str, Any] | None = None


def _load_def(conn: Connection, def_id: int) -> RowMapping:
    row = conn.execute(select(recon_batch_def).where(recon_batch_def.c.ID == def_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.BATCH_NOT_FOUND, f"Không tìm thấy bộ đối soát với id {def_id}.")
    return row


def _load_item(conn: Connection, item_id: int) -> RowMapping:
    row = conn.execute(select(recon_batch_def_item).where(recon_batch_def_item.c.ID == item_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy mục trong bộ với id {item_id}.")
    return row


def _require_editable_def(row: RowMapping) -> None:
    if row["STATUS"] == "ARCHIVED":
        raise ServiceError(ErrorCode.BATCH_NOT_ACTIVE, f"Bộ đối soát {row['CODE']} đã lưu trữ, không sửa được.")


def _active_template(conn: Connection, template_id: int) -> tuple[RowMapping, RowMapping, TemplateConfig]:
    tmpl = conn.execute(select(recon_template).where(recon_template.c.ID == template_id)).mappings().first()
    if tmpl is None:
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template với id {template_id}.")
    if tmpl["STATUS"] != "ACTIVE":
        raise ServiceError(
            ErrorCode.BATCH_TEMPLATE_NOT_ACTIVE,
            f"Template {tmpl['CODE']} chưa kích hoạt (trạng thái {tmpl['STATUS']}).",
        )
    ver = (
        conn.execute(
            select(recon_template_version)
            .where(
                recon_template_version.c.TEMPLATE_ID == template_id,
                recon_template_version.c.STATUS == "ACTIVE",
            )
            .order_by(recon_template_version.c.VERSION.desc())
        )
        .mappings()
        .first()
    )
    if ver is None:
        raise ServiceError(ErrorCode.BATCH_TEMPLATE_NOT_ACTIVE, f"Template {tmpl['CODE']} chưa có phiên bản kích hoạt.")
    raw_cfg = ver["CONFIG_JSON"]
    config = TemplateConfig.model_validate(raw_cfg if isinstance(raw_cfg, dict) else json.loads(str(raw_cfg)))
    return tmpl, ver, config


def _validate_override(config: TemplateConfig, override: dict[str, Any] | None) -> dict[str, Any]:
    """Kiểm tra ghi đè tham số: tham số phải có trong template, công thức
    phải đúng cú pháp (kiểm bằng kỳ giả 2026-01; lỗi kiểu chỉ lộ khi
    tính với kỳ thật ở preview/chạy)."""
    override = override or {}
    known = {p.name for p in config.db_source.params} | {"p_from", "p_to"}
    for key in override:
        if key not in known:
            raise ServiceError(ErrorCode.BATCH_PARAM_UNKNOWN, f"Tham số {key} không có trong template.")
    for value in override.values():
        if isinstance(value, str):
            resolve(value, "2026-01")
    return override


def _def_dict(row: RowMapping, cnt_items: int = 0) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "code": str(row["CODE"]),
        "name": str(row["NAME"]),
        "description": row["DESCRIPTION"],
        "status": str(row["STATUS"]),
        "max_parallel_per_ds": int(row["MAX_PARALLEL_PER_DS"]),
        "owner_id": int(row["OWNER_ID"]),
        "cnt_items": cnt_items,
        "row_version": int(row["ROW_VERSION"]),
        "created_at": row["CREATED_AT"],
        "updated_at": row["UPDATED_AT"],
    }


def _item_dict(
    row: RowMapping,
    template: RowMapping | None = None,
    template_version: int | None = None,
) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "batch_def_id": int(row["BATCH_DEF_ID"]),
        "template_id": int(row["TEMPLATE_ID"]),
        "template_code": str(template["CODE"]) if template is not None else None,
        "template_name": str(template["NAME"]) if template is not None else None,
        "template_status": str(template["STATUS"]) if template is not None else None,
        "template_version": template_version,
        "seq_no": int(row["SEQ_NO"]),
        "priority": int(row["PRIORITY"]),
        "profile_code": row["PROFILE_CODE"],
        "data_source_id": row["DATA_SOURCE_ID"],
        "file_pattern": str(row["FILE_PATTERN"]),
        "multi_file": row["MULTI_FILE"] == "Y",
        "is_required": row["IS_REQUIRED"] == "Y",
        "params_override": dict(row["PARAMS_OVERRIDE_JSON"] or {}),
        "is_active": row["IS_ACTIVE"] == "Y",
        "row_version": int(row["ROW_VERSION"]),
    }


def _items_with_templates(conn: Connection, def_id: int) -> list[dict[str, Any]]:
    rows = (
        conn.execute(
            select(recon_batch_def_item)
            .where(
                recon_batch_def_item.c.BATCH_DEF_ID == def_id,
                recon_batch_def_item.c.IS_ACTIVE == "Y",
            )
            .order_by(recon_batch_def_item.c.SEQ_NO)
        )
        .mappings()
        .all()
    )
    if not rows:
        return []
    tmpl_ids = [int(r["TEMPLATE_ID"]) for r in rows]
    tmpls = {
        int(t["ID"]): t
        for t in conn.execute(select(recon_template).where(recon_template.c.ID.in_(tmpl_ids))).mappings().all()
    }
    vers = {
        int(v["TEMPLATE_ID"]): int(v["VERSION"])
        for v in conn.execute(
            select(recon_template_version).where(
                recon_template_version.c.TEMPLATE_ID.in_(tmpl_ids),
                recon_template_version.c.STATUS == "ACTIVE",
            )
        )
        .mappings()
        .all()
    }
    return [_item_dict(r, tmpls.get(int(r["TEMPLATE_ID"])), vers.get(int(r["TEMPLATE_ID"]))) for r in rows]


def _serialize_params(resolved: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in resolved.items():
        if isinstance(value, (datetime, date)):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _preview_items(conn: Connection, def_id: int, period: str) -> list[dict[str, Any]]:
    items = _items_with_templates(conn, def_id)
    result: list[dict[str, Any]] = []
    for item in items:
        entry: dict[str, Any] = {
            "item_id": item["id"],
            "template_id": item["template_id"],
            "template_code": item["template_code"],
            "params": {},
            "errors": [],
        }
        try:
            _tmpl, _ver, config = _active_template(conn, item["template_id"])
        except ServiceError as exc:
            entry["errors"].append({"code": str(exc.code), "message": exc.message})
            result.append(entry)
            continue
        try:
            resolved = resolve_params(config.db_source.params, item["params_override"], None, period)
        except ServiceError as exc:
            entry["errors"].append({"code": str(exc.code), "message": exc.message})
            result.append(entry)
            continue
        entry["params"] = _serialize_params(resolved)
        result.append(entry)
    return result


@service
@requires_menu("batch_def")
def list_batch_defs(ctx: Ctx, q: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    """Danh sách bộ đối soát (mọi vai trò có menu batch_def)."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        stmt = select(recon_batch_def).order_by(recon_batch_def.c.CODE)
        if q:
            like = f"%{q}%"
            stmt = stmt.where((recon_batch_def.c.CODE.like(like)) | (recon_batch_def.c.NAME.like(like)))
        if status:
            stmt = stmt.where(recon_batch_def.c.STATUS == status)
        rows = conn.execute(stmt).mappings().all()
        counts: dict[int, int] = dict(
            conn.execute(
                select(recon_batch_def_item.c.BATCH_DEF_ID, func.count())
                .where(recon_batch_def_item.c.IS_ACTIVE == "Y")
                .group_by(recon_batch_def_item.c.BATCH_DEF_ID)
            ).all()
        )
    return [_def_dict(r, counts.get(int(r["ID"]), 0)) for r in rows]


@service
@requires_menu("batch_def")
def get_batch_def(ctx: Ctx, def_id: int) -> dict[str, Any]:
    """Chi tiết bộ đối soát kèm các mục đang hoạt động."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        row = _load_def(conn, def_id)
        items = _items_with_templates(conn, def_id)
    data = _def_dict(row, len(items))
    data["items"] = items
    return data


@service
@requires_menu("batch_def")
def create_batch_def(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Tạo bộ đối soát mới (ADMIN, TEMPLATE_OWNER)."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    dto = BatchDefCreate(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        exists = conn.execute(select(recon_batch_def.c.ID).where(recon_batch_def.c.CODE == dto.code)).first()
        if exists is not None:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã bộ đối soát {dto.code} đã tồn tại.")
        res = conn.execute(
            recon_batch_def.insert().values(
                CODE=dto.code,
                NAME=dto.name,
                DESCRIPTION=dto.description,
                STATUS="DRAFT",
                MAX_PARALLEL_PER_DS=dto.max_parallel_per_ds,
                OWNER_ID=int(ctx.user_id),
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        pk = res.inserted_primary_key
        if pk is None:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không tạo được bộ đối soát.")
        def_id = int(pk[0])
        write_audit_log(
            conn=conn,
            entity="RECON_BATCH_DEF",
            entity_id=def_id,
            action="CREATE_BATCH_DEF",
            actor=ctx.username,
            new_data={"code": dto.code, "name": dto.name},
            now=now,
        )
        row = conn.execute(select(recon_batch_def).where(recon_batch_def.c.ID == def_id)).mappings().first()
        assert row is not None
        return _def_dict(row, 0)


@service
@requires_menu("batch_def")
def update_batch_def(ctx: Ctx, def_id: int, payload: dict[str, Any], row_version: int | None = None) -> dict[str, Any]:
    """Sửa bộ đối soát; khóa lạc quan ROW_VERSION."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    dto = BatchDefUpdate(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = _load_def(conn, def_id)
        _require_editable_def(row)
        if row_version is not None and int(row["ROW_VERSION"]) != row_version:
            raise ServiceError(ErrorCode.STALE_DATA, "Bộ đối soát đã bị thay đổi, tải lại rồi sửa tiếp.")
        values: dict[str, Any] = {"UPDATED_BY": ctx.username, "UPDATED_AT": now}
        if dto.name is not None:
            values["NAME"] = dto.name
        if dto.description is not None:
            values["DESCRIPTION"] = dto.description
        if dto.max_parallel_per_ds is not None:
            values["MAX_PARALLEL_PER_DS"] = dto.max_parallel_per_ds
        values["ROW_VERSION"] = int(row["ROW_VERSION"]) + 1
        conn.execute(recon_batch_def.update().where(recon_batch_def.c.ID == def_id).values(**values))
        write_audit_log(
            conn=conn,
            entity="RECON_BATCH_DEF",
            entity_id=def_id,
            action="UPDATE_BATCH_DEF",
            actor=ctx.username,
            old_data={"code": str(row["CODE"]), "name": str(row["NAME"])},
            new_data={"code": str(row["CODE"]), "name": dto.name or str(row["NAME"])},
            now=now,
        )
        updated = conn.execute(select(recon_batch_def).where(recon_batch_def.c.ID == def_id)).mappings().first()
        assert updated is not None
        items = _items_with_templates(conn, def_id)
        return _def_dict(updated, len(items))


@service
@requires_menu("batch_def")
def archive_batch_def(ctx: Ctx, def_id: int) -> dict[str, Any]:
    """Lưu trữ bộ đối soát (STATUS='ARCHIVED')."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = _load_def(conn, def_id)
        if row["STATUS"] != "ARCHIVED":
            conn.execute(
                recon_batch_def.update()
                .where(recon_batch_def.c.ID == def_id)
                .values(
                    STATUS="ARCHIVED",
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=int(row["ROW_VERSION"]) + 1,
                )
            )
            write_audit_log(
                conn=conn,
                entity="RECON_BATCH_DEF",
                entity_id=def_id,
                action="ARCHIVE_BATCH_DEF",
                actor=ctx.username,
                old_data={"code": str(row["CODE"]), "status": str(row["STATUS"])},
                new_data={"code": str(row["CODE"]), "status": "ARCHIVED"},
                now=now,
            )
        updated = conn.execute(select(recon_batch_def).where(recon_batch_def.c.ID == def_id)).mappings().first()
        assert updated is not None
        items = _items_with_templates(conn, def_id)
        return _def_dict(updated, len(items))


@service
@requires_menu("batch_def")
def activate_batch_def(ctx: Ctx, def_id: int) -> dict[str, Any]:
    """Kích hoạt bộ đối soát (DRAFT → ACTIVE).

    Yêu cầu (spec 10a mục 1): ≥ 1 mục đang hoạt động, mọi mục có mẫu
    tên file, không có lỗi tham số với kỳ hiện tại.
    """
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    engine = get_recon_engine()
    now = _now()
    current_period = now.strftime("%Y-%m")
    with engine.begin() as conn:
        row = _load_def(conn, def_id)
        if row["STATUS"] == "ARCHIVED":
            raise ServiceError(
                ErrorCode.BATCH_NOT_ACTIVE, f"Bộ đối soát {row['CODE']} đã lưu trữ, không kích hoạt được."
            )
        if row["STATUS"] == "ACTIVE":
            items = _items_with_templates(conn, def_id)
            return _def_dict(row, len(items))
        items = _items_with_templates(conn, def_id)
        if not items:
            raise ServiceError(
                ErrorCode.BATCH_NOT_ACTIVE, "Bộ đối soát chưa có mục nào, thêm template trước khi kích hoạt."
            )
        for item in items:
            if not str(item["file_pattern"]).strip():
                raise ServiceError(
                    ErrorCode.BATCH_NOT_ACTIVE,
                    f"Mục {item['template_code']} chưa có mẫu tên file.",
                )
        previews = _preview_items(conn, def_id, current_period)
        for preview in previews:
            if preview["errors"]:
                err = preview["errors"][0]
                raise ServiceError(
                    ErrorCode.BATCH_NOT_ACTIVE,
                    f"Mục {preview['template_code']} lỗi tham số: {err['message']}",
                )
        conn.execute(
            recon_batch_def.update()
            .where(recon_batch_def.c.ID == def_id)
            .values(
                STATUS="ACTIVE",
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=int(row["ROW_VERSION"]) + 1,
            )
        )
        write_audit_log(
            conn=conn,
            entity="RECON_BATCH_DEF",
            entity_id=def_id,
            action="ACTIVATE_BATCH_DEF",
            actor=ctx.username,
            old_data={"code": str(row["CODE"]), "status": "DRAFT"},
            new_data={"code": str(row["CODE"]), "status": "ACTIVE"},
            now=now,
        )
        updated = conn.execute(select(recon_batch_def).where(recon_batch_def.c.ID == def_id)).mappings().first()
        assert updated is not None
        return _def_dict(updated, len(items))


@service
@requires_menu("batch_def")
def add_batch_def_items(ctx: Ctx, def_id: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Thêm nhiều template vào bộ (ADMIN, TEMPLATE_OWNER)."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    engine = get_recon_engine()
    now = _now()
    added: list[dict[str, Any]] = []
    with engine.begin() as conn:
        row = _load_def(conn, def_id)
        _require_editable_def(row)
        seq_no = conn.execute(
            select(func.coalesce(func.max(recon_batch_def_item.c.SEQ_NO), 0)).where(
                recon_batch_def_item.c.BATCH_DEF_ID == def_id
            )
        ).scalar_one()
        for raw in items:
            dto = BatchDefItemCreate(**raw)
            pattern = dto.file_pattern.strip()
            if not pattern:
                raise ServiceError(ErrorCode.BATCH_ITEM_PATTERN_REQUIRED, "Mẫu tên file là bắt buộc trước khi lưu.")
            tmpl, _ver, config = _active_template(conn, dto.template_id)
            override = _validate_override(config, dto.params_override)
            existing = (
                conn.execute(
                    select(recon_batch_def_item).where(
                        recon_batch_def_item.c.BATCH_DEF_ID == def_id,
                        recon_batch_def_item.c.TEMPLATE_ID == dto.template_id,
                    )
                )
                .mappings()
                .first()
            )
            if existing is not None:
                if existing["IS_ACTIVE"] == "Y":
                    raise ServiceError(
                        ErrorCode.BATCH_TEMPLATE_EXISTS,
                        f"Template {tmpl['CODE']} đã có trong bộ đối soát.",
                    )
                # Thêm lại mục đã gỡ mềm: bật lại mục cũ với cấu hình mới.
                seq_no = int(existing["SEQ_NO"])
                conn.execute(
                    recon_batch_def_item.update()
                    .where(recon_batch_def_item.c.ID == existing["ID"])
                    .values(
                        FILE_PATTERN=pattern,
                        MULTI_FILE="Y" if dto.multi_file else "N",
                        IS_REQUIRED="Y" if dto.is_required else "N",
                        PRIORITY=dto.priority,
                        PROFILE_CODE=dto.profile_code,
                        DATA_SOURCE_ID=dto.data_source_id,
                        PARAMS_OVERRIDE_JSON=override or None,
                        IS_ACTIVE="Y",
                        UPDATED_BY=ctx.username,
                        UPDATED_AT=now,
                        ROW_VERSION=int(existing["ROW_VERSION"]) + 1,
                    )
                )
                write_audit_log(
                    conn=conn,
                    entity="RECON_BATCH_DEF_ITEM",
                    entity_id=int(existing["ID"]),
                    action="ADD_BATCH_DEF_ITEM",
                    actor=ctx.username,
                    new_data={"def_id": def_id, "template_code": str(tmpl["CODE"]), "reactivated": True},
                    now=now,
                )
                updated = (
                    conn.execute(select(recon_batch_def_item).where(recon_batch_def_item.c.ID == existing["ID"]))
                    .mappings()
                    .first()
                )
                assert updated is not None
                added.append(_item_dict(updated, tmpl))
                continue
            seq_no = int(seq_no) + 1
            res = conn.execute(
                recon_batch_def_item.insert().values(
                    BATCH_DEF_ID=def_id,
                    TEMPLATE_ID=dto.template_id,
                    SEQ_NO=seq_no,
                    PRIORITY=dto.priority,
                    PROFILE_CODE=dto.profile_code,
                    DATA_SOURCE_ID=dto.data_source_id,
                    FILE_PATTERN=pattern,
                    MULTI_FILE="Y" if dto.multi_file else "N",
                    IS_REQUIRED="Y" if dto.is_required else "N",
                    PARAMS_OVERRIDE_JSON=override or None,
                    IS_ACTIVE="Y",
                    CREATED_BY=ctx.username,
                    CREATED_AT=now,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=1,
                )
            )
            item_pk = res.inserted_primary_key
            if item_pk is None:
                raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không thêm được template vào bộ.")
            item_id = int(item_pk[0])
            write_audit_log(
                conn=conn,
                entity="RECON_BATCH_DEF_ITEM",
                entity_id=item_id,
                action="ADD_BATCH_DEF_ITEM",
                actor=ctx.username,
                new_data={"def_id": def_id, "template_code": str(tmpl["CODE"])},
                now=now,
            )
            new_row = (
                conn.execute(select(recon_batch_def_item).where(recon_batch_def_item.c.ID == item_id))
                .mappings()
                .first()
            )
            assert new_row is not None
            added.append(_item_dict(new_row, tmpl))
    return added


@service
@requires_menu("batch_def")
def update_batch_def_item(
    ctx: Ctx, item_id: int, payload: dict[str, Any], row_version: int | None = None
) -> dict[str, Any]:
    """Sửa mục trong bộ; khóa lạc quan ROW_VERSION."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    dto = BatchDefItemUpdate(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = _load_item(conn, item_id)
        def_row = _load_def(conn, int(row["BATCH_DEF_ID"]))
        _require_editable_def(def_row)
        if row_version is not None and int(row["ROW_VERSION"]) != row_version:
            raise ServiceError(ErrorCode.STALE_DATA, "Mục trong bộ đã bị thay đổi, tải lại rồi sửa tiếp.")
        values: dict[str, Any] = {"UPDATED_BY": ctx.username, "UPDATED_AT": now}
        if dto.file_pattern is not None:
            pattern = dto.file_pattern.strip()
            if not pattern:
                raise ServiceError(ErrorCode.BATCH_ITEM_PATTERN_REQUIRED, "Mẫu tên file là bắt buộc trước khi lưu.")
            values["FILE_PATTERN"] = pattern
        if dto.multi_file is not None:
            values["MULTI_FILE"] = "Y" if dto.multi_file else "N"
        if dto.is_required is not None:
            values["IS_REQUIRED"] = "Y" if dto.is_required else "N"
        if dto.priority is not None:
            values["PRIORITY"] = dto.priority
        if dto.profile_code is not None:
            values["PROFILE_CODE"] = dto.profile_code
        if dto.data_source_id is not None:
            values["DATA_SOURCE_ID"] = dto.data_source_id
        if dto.params_override is not None:
            try:
                _tmpl, _ver, config = _active_template(conn, int(row["TEMPLATE_ID"]))
            except ServiceError:
                config = None
            if config is not None:
                values["PARAMS_OVERRIDE_JSON"] = _validate_override(config, dto.params_override) or None
            else:
                values["PARAMS_OVERRIDE_JSON"] = dto.params_override or None
        values["ROW_VERSION"] = int(row["ROW_VERSION"]) + 1
        conn.execute(recon_batch_def_item.update().where(recon_batch_def_item.c.ID == item_id).values(**values))
        write_audit_log(
            conn=conn,
            entity="RECON_BATCH_DEF_ITEM",
            entity_id=item_id,
            action="UPDATE_BATCH_DEF_ITEM",
            actor=ctx.username,
            old_data={"def_id": int(row["BATCH_DEF_ID"]), "template_id": int(row["TEMPLATE_ID"])},
            new_data={"def_id": int(row["BATCH_DEF_ID"]), "template_id": int(row["TEMPLATE_ID"])},
            now=now,
        )
        updated = (
            conn.execute(select(recon_batch_def_item).where(recon_batch_def_item.c.ID == item_id)).mappings().first()
        )
        assert updated is not None
        tmpl = (
            conn.execute(select(recon_template).where(recon_template.c.ID == updated["TEMPLATE_ID"])).mappings().first()
        )
        return _item_dict(updated, tmpl)


@service
@requires_menu("batch_def")
def remove_batch_def_item(ctx: Ctx, item_id: int) -> dict[str, Any]:
    """Gỡ template khỏi bộ: xóa hẳn nếu chưa có lần chạy tham chiếu,
    xóa mềm (IS_ACTIVE='N') nếu đã có."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = _load_item(conn, item_id)
        def_row = _load_def(conn, int(row["BATCH_DEF_ID"]))
        _require_editable_def(def_row)
        tmpl = conn.execute(select(recon_template).where(recon_template.c.ID == row["TEMPLATE_ID"])).mappings().first()
        referenced = conn.execute(
            select(recon_batch_run_item.c.ID).where(recon_batch_run_item.c.BATCH_DEF_ITEM_ID == item_id)
        ).first()
        data = _item_dict(row, tmpl)
        if referenced is None:
            conn.execute(recon_batch_def_item.delete().where(recon_batch_def_item.c.ID == item_id))
        else:
            conn.execute(
                recon_batch_def_item.update()
                .where(recon_batch_def_item.c.ID == item_id)
                .values(
                    IS_ACTIVE="N",
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=int(row["ROW_VERSION"]) + 1,
                )
            )
            data["is_active"] = False
        write_audit_log(
            conn=conn,
            entity="RECON_BATCH_DEF_ITEM",
            entity_id=item_id,
            action="REMOVE_BATCH_DEF_ITEM",
            actor=ctx.username,
            old_data={"def_id": int(row["BATCH_DEF_ID"]), "template_id": int(row["TEMPLATE_ID"])},
            new_data={"def_id": int(row["BATCH_DEF_ID"]), "is_active": data["is_active"]},
            now=now,
        )
        return data


@service
@requires_menu("batch_def")
def addable_templates(
    ctx: Ctx, def_id: int, q: str | None = None, include_unavailable: bool = False
) -> list[dict[str, Any]]:
    """Template có thể thêm vào bộ, kèm lý do khi không thêm được."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        _load_def(conn, def_id)
        stmt = select(recon_template).order_by(recon_template.c.CODE)
        if q:
            like = f"%{q}%"
            stmt = stmt.where((recon_template.c.CODE.like(like)) | (recon_template.c.NAME.like(like)))
        templates = conn.execute(stmt).mappings().all()
        in_def = {
            int(tid)
            for tid in conn.execute(
                select(recon_batch_def_item.c.TEMPLATE_ID).where(
                    recon_batch_def_item.c.BATCH_DEF_ID == def_id,
                    recon_batch_def_item.c.IS_ACTIVE == "Y",
                )
            )
            .scalars()
            .all()
        }
        tmpl_ids = [int(t["ID"]) for t in templates]
        vers: dict[int, RowMapping] = {}
        if tmpl_ids:
            vers = {
                int(v["TEMPLATE_ID"]): v
                for v in conn.execute(
                    select(recon_template_version).where(
                        recon_template_version.c.TEMPLATE_ID.in_(tmpl_ids),
                        recon_template_version.c.STATUS == "ACTIVE",
                    )
                )
                .mappings()
                .all()
            }
    result: list[dict[str, Any]] = []
    for tmpl in templates:
        tid = int(tmpl["ID"])
        ver = vers.get(tid)
        if tid in in_def:
            addable, reason = False, "Đã có trong bộ"
        elif tmpl["STATUS"] == "DRAFT":
            addable, reason = False, "Cần dry-run và kích hoạt trước"
        elif tmpl["STATUS"] == "ARCHIVED":
            addable, reason = False, "Template đã lưu trữ"
        elif tmpl["STATUS"] == "ACTIVE" and ver is None:
            addable, reason = False, "Template chưa có phiên bản kích hoạt"
        else:
            addable, reason = True, None
        if not include_unavailable and not addable:
            continue
        result.append(
            {
                "template_id": tid,
                "code": str(tmpl["CODE"]),
                "name": str(tmpl["NAME"]),
                "status": str(tmpl["STATUS"]),
                "version": int(ver["VERSION"]) if ver is not None else None,
                "data_source_id": int(ver["DATA_SOURCE_ID"]) if ver is not None and ver["DATA_SOURCE_ID"] else None,
                "addable": addable,
                "reason": reason,
            }
        )
    return result


@service
@requires_menu("batch_def")
def preview_params(ctx: Ctx, def_id: int, period: str) -> dict[str, Any]:
    """Giá trị tham số đã tính của mọi mục với một kỳ thử."""
    parse_period(period)
    engine = get_recon_engine()
    with engine.connect() as conn:
        _load_def(conn, def_id)
        items = _preview_items(conn, def_id, period)
    return {"def_id": def_id, "period": period, "items": items}
