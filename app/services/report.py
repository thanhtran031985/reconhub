"""Service Report Master — task 21, spec 12/12a.

CRUD cho RECON_REPORT (định nghĩa báo cáo dùng chung theo menu) và
yêu thích theo người dùng. Ghi metadata cần menu report_admin; đọc
cần menu report_center. Người thường chỉ thấy report đang hiển thị và
đang dùng; ADMIN thấy tất cả.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Connection, select

from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_report, recon_rpt_favorite
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,59}$")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReportCreate(BaseModel):
    """Payload tạo Report Master (wizard bước 1)."""

    code: str = Field(pattern=_CODE_RE)
    name: str = Field(min_length=1, max_length=200)
    category_code: str | None = Field(default=None, max_length=60)
    owner: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    default_favorite: bool = False
    is_visible: bool = True


class ReportUpdate(BaseModel):
    """Payload sửa Report Master (không đổi CODE)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    category_code: str | None = Field(default=None, max_length=60)
    owner: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    default_favorite: bool | None = None
    is_visible: bool | None = None
    is_active: bool | None = None


def _report_dict(row: Any, is_favorite: bool = False) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "code": str(row["CODE"]),
        "name": str(row["NAME"]),
        "category_code": row["CATEGORY_CODE"],
        "owner": str(row["OWNER"]),
        "description": row["DESCRIPTION"],
        "default_favorite": row["DEFAULT_FAVORITE"] == "Y",
        "is_visible": row["IS_VISIBLE"] == "Y",
        "is_active": row["IS_ACTIVE"] == "Y",
        "is_favorite": is_favorite,
        "row_version": int(row["ROW_VERSION"]),
    }


def load_report_row(conn: Connection, report_id: int, admin: bool) -> Any:
    """Đọc dòng RECON_REPORT; người thường chỉ thấy report hiển thị."""
    stmt = select(recon_report).where(recon_report.c.ID == report_id)
    if not admin:
        stmt = stmt.where(recon_report.c.IS_VISIBLE == "Y", recon_report.c.IS_ACTIVE == "Y")
    row = conn.execute(stmt).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy báo cáo.")
    return row


@service
@requires_menu("report_center")
def list_reports(ctx: Ctx) -> list[dict[str, Any]]:
    """Danh sách Report Master; kèm cờ yêu thích của người dùng."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        stmt = select(recon_report)
        if not admin:
            stmt = stmt.where(recon_report.c.IS_VISIBLE == "Y", recon_report.c.IS_ACTIVE == "Y")
        rows = conn.execute(stmt.order_by(recon_report.c.CODE)).mappings().all()
        fav_ids = {
            int(r[0])
            for r in conn.execute(
                select(recon_rpt_favorite.c.REPORT_ID).where(
                    recon_rpt_favorite.c.USER_ID == ctx.user_id
                )
            ).all()
        }
        return [_report_dict(row, int(row["ID"]) in fav_ids) for row in rows]


@service
@requires_menu("report_center")
def get_report(ctx: Ctx, report_id: int) -> dict[str, Any]:
    """Chi tiết một Report Master."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        row = load_report_row(conn, report_id, admin)
        fav = (
            conn.execute(
                select(recon_rpt_favorite.c.REPORT_ID).where(
                    recon_rpt_favorite.c.USER_ID == ctx.user_id,
                    recon_rpt_favorite.c.REPORT_ID == report_id,
                )
            ).first()
            is not None
        )
        return _report_dict(row, fav)


@service
@requires_menu("report_admin")
def create_report(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Tạo Report Master mới (chỉ Admin)."""
    dto = ReportCreate(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        exists = conn.execute(
            select(recon_report.c.ID).where(recon_report.c.CODE == dto.code)
        ).first()
        if exists is not None:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã báo cáo {dto.code} đã tồn tại.")
        res = conn.execute(
            recon_report.insert().values(
                CODE=dto.code,
                NAME=dto.name,
                CATEGORY_CODE=dto.category_code,
                OWNER=dto.owner,
                DESCRIPTION=dto.description,
                DEFAULT_FAVORITE="Y" if dto.default_favorite else "N",
                IS_VISIBLE="Y" if dto.is_visible else "N",
                IS_ACTIVE="Y",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        pk = res.inserted_primary_key
        if pk is None:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không tạo được báo cáo.")
        row = conn.execute(
            select(recon_report).where(recon_report.c.ID == int(pk[0]))
        ).mappings().first()
        assert row is not None
        return _report_dict(row)


@service
@requires_menu("report_admin")
def update_report(
    ctx: Ctx, report_id: int, payload: dict[str, Any], row_version: int | None = None
) -> dict[str, Any]:
    """Sửa Report Master; khóa lạc quan ROW_VERSION (chỉ kiểm khi truyền)."""
    dto = ReportUpdate(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = load_report_row(conn, report_id, admin=True)
        if row_version is not None and int(row["ROW_VERSION"]) != row_version:
            raise ServiceError(
                ErrorCode.STALE_DATA, "Báo cáo đã bị thay đổi, tải lại rồi sửa tiếp."
            )
        values: dict[str, Any] = {"UPDATED_BY": ctx.username, "UPDATED_AT": now}
        if dto.name is not None:
            values["NAME"] = dto.name
        if dto.category_code is not None:
            values["CATEGORY_CODE"] = dto.category_code
        if dto.owner is not None:
            values["OWNER"] = dto.owner
        if dto.description is not None:
            values["DESCRIPTION"] = dto.description
        if dto.default_favorite is not None:
            values["DEFAULT_FAVORITE"] = "Y" if dto.default_favorite else "N"
        if dto.is_visible is not None:
            values["IS_VISIBLE"] = "Y" if dto.is_visible else "N"
        if dto.is_active is not None:
            values["IS_ACTIVE"] = "Y" if dto.is_active else "N"
        values["ROW_VERSION"] = int(row["ROW_VERSION"]) + 1
        conn.execute(
            recon_report.update().where(recon_report.c.ID == report_id).values(**values)
        )
        updated = conn.execute(
            select(recon_report).where(recon_report.c.ID == report_id)
        ).mappings().first()
        assert updated is not None
        return _report_dict(updated)


@service
@requires_menu("report_admin")
def archive_report(ctx: Ctx, report_id: int) -> dict[str, Any]:
    """Lưu trữ report (IS_ACTIVE='N'); người thường không còn thấy."""
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = load_report_row(conn, report_id, admin=True)
        conn.execute(
            recon_report.update()
            .where(recon_report.c.ID == report_id)
            .values(IS_ACTIVE="N", UPDATED_BY=ctx.username, UPDATED_AT=now, ROW_VERSION=int(row["ROW_VERSION"]) + 1)
        )
        updated = conn.execute(
            select(recon_report).where(recon_report.c.ID == report_id)
        ).mappings().first()
        assert updated is not None
        return _report_dict(updated)


@service
@requires_menu("report_center")
def set_report_favorite(ctx: Ctx, report_id: int, favorite: bool) -> dict[str, Any]:
    """Thêm/bỏ yêu thích một report của chính người dùng."""
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        admin = is_admin(ctx, engine)
        load_report_row(conn, report_id, admin)
        if favorite:
            exists = conn.execute(
                select(recon_rpt_favorite.c.REPORT_ID).where(
                    recon_rpt_favorite.c.USER_ID == ctx.user_id,
                    recon_rpt_favorite.c.REPORT_ID == report_id,
                )
            ).first()
            if exists is None:
                conn.execute(
                    recon_rpt_favorite.insert().values(
                        USER_ID=ctx.user_id, REPORT_ID=report_id, CREATED_AT=now
                    )
                )
        else:
            conn.execute(
                recon_rpt_favorite.delete().where(
                    recon_rpt_favorite.c.USER_ID == ctx.user_id,
                    recon_rpt_favorite.c.REPORT_ID == report_id,
                )
            )
        return {"report_id": report_id, "is_favorite": favorite}
