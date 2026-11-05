from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, desc, func, or_, select, update

from app.core.audit import write_audit_log
from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_issue,
    recon_issue_reason,
    recon_result_row,
    recon_run,
    recon_template,
    recon_user,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service

ALL_ROLES = (Role.VIEWER, Role.OPERATOR, Role.TEMPLATE_OWNER, Role.ADMIN)
MUTATION_ROLES = (Role.OPERATOR, Role.TEMPLATE_OWNER, Role.ADMIN)
VALID_ISSUE_STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED", "ACCEPTED"}

DEFAULT_ISSUE_REASONS = [
    ("ROUNDING", "Lệch làm tròn số thập phân"),
    ("TIMING", "Lệch thời điểm ghi nhận giao dịch"),
    ("SYSTEM_BUG", "Lỗi hệ thống tác nghiệp/billing"),
    ("DATA_INPUT", "Sai sót nhập liệu thủ công"),
    ("POLICY_EXCEPTION", "Ngoại lệ chính sách / Phê duyệt đặc biệt"),
    ("OTHER", "Nguyên nhân khác"),
]


def ensure_default_reasons(conn: Connection) -> None:
    """Nạp các lý do chênh lệch chuẩn nếu chưa có (idempotent)."""
    for code, label in DEFAULT_ISSUE_REASONS:
        exists = conn.execute(select(recon_issue_reason.c.CODE).where(recon_issue_reason.c.CODE == code)).scalar()
        if not exists:
            conn.execute(
                recon_issue_reason.insert().values(
                    CODE=code,
                    LABEL=label,
                    IS_ACTIVE="Y",
                )
            )


@service
def list_reasons(ctx: Ctx) -> list[dict[str, Any]]:
    """Lấy danh sách các nguyên nhân chênh lệch đang hoạt động."""
    require_role(ctx, *ALL_ROLES)
    engine = get_recon_engine()
    with engine.begin() as conn:
        ensure_default_reasons(conn)
        rows = (
            conn.execute(
                select(recon_issue_reason)
                .where(recon_issue_reason.c.IS_ACTIVE == "Y")
                .order_by(recon_issue_reason.c.CODE)
            )
            .mappings()
            .all()
        )
    result = []
    for r in rows:
        d = dict(r)
        code = d.get("CODE") or d.get("code")
        label = d.get("LABEL") or d.get("label")
        active = d.get("IS_ACTIVE") or d.get("is_active") or "Y"
        result.append(
            {
                "CODE": code,
                "code": code,
                "LABEL": label,
                "label": label,
                "IS_ACTIVE": active,
                "is_active": active,
            }
        )
    return result


@service
def list_assignees(ctx: Ctx) -> list[dict[str, Any]]:
    """Lấy danh sách người dùng có thể gán xử lý chênh lệch."""
    require_role(ctx, *ALL_ROLES)
    engine = get_recon_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(
                    recon_user.c.ID.label("id"),
                    recon_user.c.USERNAME.label("username"),
                    recon_user.c.FULL_NAME.label("full_name"),
                )
                .where(recon_user.c.IS_ACTIVE == "Y")
                .order_by(recon_user.c.FULL_NAME)
            )
            .mappings()
            .all()
        )
    return [
        {
            "ID": r["id"],
            "id": r["id"],
            "USERNAME": r["username"],
            "username": r["username"],
            "FULL_NAME": r["full_name"],
            "full_name": r["full_name"],
        }
        for r in rows
    ]


@service
def update_issue_by_id(
    ctx: Ctx,
    issue_id: int,
    status: str | None = None,
    reason_code: str | None = None,
    assignee_id: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Cập nhật trực tiếp một issue theo ID."""
    require_role(ctx, *MUTATION_ROLES)
    if status is not None and status not in VALID_ISSUE_STATUSES:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Trạng thái '{status}' không hợp lệ. Phải là một trong: {', '.join(VALID_ISSUE_STATUSES)}.",
        )
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        issue = conn.execute(select(recon_issue).where(recon_issue.c.ID == issue_id)).mappings().first()
        if not issue:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy Issue với ID {issue_id}.")

        upd_values: dict[str, Any] = {
            "UPDATED_BY": ctx.username,
            "UPDATED_AT": now,
            "ROW_VERSION": recon_issue.c.ROW_VERSION + 1,
        }
        if status is not None:
            upd_values["STATUS"] = status
        if reason_code is not None:
            upd_values["REASON_CODE"] = reason_code
        if assignee_id is not None:
            upd_values["ASSIGNEE_ID"] = assignee_id
        if note is not None:
            upd_values["NOTE"] = note

        conn.execute(update(recon_issue).where(recon_issue.c.ID == issue_id).values(**upd_values))

        write_audit_log(
            conn=conn,
            entity="ISSUE",
            entity_id=str(issue_id),
            action="UPDATE_ISSUE",
            actor=ctx.username,
            old_data=dict(issue),
            new_data={k: v for k, v in upd_values.items() if k != "ROW_VERSION"},
            now=now,
        )

    res = get_issue(ctx, issue_id=issue_id)
    return dict(res.data) if res.data else {}


@service
def bulk_update_issues_by_ids(
    ctx: Ctx,
    issue_ids: list[int],
    status: str | None = None,
    reason_code: str | None = None,
    assignee_id: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Cập nhật hàng loạt nhiều issue theo danh sách ID."""
    require_role(ctx, *MUTATION_ROLES)
    if not issue_ids:
        return {"count": 0, "updated_issues": []}

    if status is not None and status not in VALID_ISSUE_STATUSES:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Trạng thái '{status}' không hợp lệ. Phải là một trong: {', '.join(VALID_ISSUE_STATUSES)}.",
        )

    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    upd_values: dict[str, Any] = {
        "UPDATED_BY": ctx.username,
        "UPDATED_AT": now,
        "ROW_VERSION": recon_issue.c.ROW_VERSION + 1,
    }
    if status is not None:
        upd_values["STATUS"] = status
    if reason_code is not None:
        upd_values["REASON_CODE"] = reason_code
    if assignee_id is not None:
        upd_values["ASSIGNEE_ID"] = assignee_id
    if note is not None:
        upd_values["NOTE"] = note

    with engine.begin() as conn:
        conn.execute(update(recon_issue).where(recon_issue.c.ID.in_(issue_ids)).values(**upd_values))

        write_audit_log(
            conn=conn,
            entity="ISSUE",
            entity_id=f"BULK_{len(issue_ids)}",
            action="BULK_UPDATE_ISSUES",
            actor=ctx.username,
            new_data={
                "issue_ids": issue_ids,
                "status": status,
                "reason_code": reason_code,
                "assignee_id": assignee_id,
            },
            now=now,
        )

    return {
        "count": len(issue_ids),
        "updated_issues": issue_ids,
    }


@service
def get_issue(ctx: Ctx, issue_id: int) -> dict[str, Any]:
    """Xem thông tin chi tiết một issue."""
    require_role(ctx, *ALL_ROLES)
    engine = get_recon_engine()
    with engine.connect() as conn:
        stmt = (
            select(
                recon_issue,
                recon_template.c.NAME.label("TEMPLATE_NAME"),
                recon_template.c.CODE.label("TEMPLATE_CODE"),
                recon_user.c.FULL_NAME.label("ASSIGNEE_NAME"),
                recon_user.c.USERNAME.label("ASSIGNEE_USERNAME"),
                recon_issue_reason.c.LABEL.label("REASON_LABEL"),
            )
            .outerjoin(recon_template, recon_issue.c.TEMPLATE_ID == recon_template.c.ID)
            .outerjoin(recon_user, recon_issue.c.ASSIGNEE_ID == recon_user.c.ID)
            .outerjoin(recon_issue_reason, recon_issue.c.REASON_CODE == recon_issue_reason.c.CODE)
            .where(recon_issue.c.ID == issue_id)
        )
        row = conn.execute(stmt).mappings().first()

    if not row:
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy Issue với ID {issue_id}.")
    return dict(row)


@service
def get_issue_for_row(ctx: Ctx, run_id: int, row_no: int) -> dict[str, Any] | None:
    """Lấy thông tin Issue (nếu có) liên kết với một dòng kết quả của run."""
    require_role(ctx, *ALL_ROLES)
    engine = get_recon_engine()
    with engine.connect() as conn:
        # Lấy thông tin run và dòng kết quả
        run_row = (
            conn.execute(select(recon_run.c.TEMPLATE_ID, recon_run.c.PROFILE_CODE).where(recon_run.c.ID == run_id))
            .mappings()
            .first()
        )
        if not run_row:
            return None

        result_row = (
            conn.execute(
                select(recon_result_row.c.KEY_HASH).where(
                    recon_result_row.c.RUN_ID == run_id,
                    recon_result_row.c.ROW_NO == row_no,
                )
            )
            .mappings()
            .first()
        )
        if not result_row:
            return None

        key_hash = result_row["KEY_HASH"]
        stmt = (
            select(
                recon_issue,
                recon_user.c.FULL_NAME.label("ASSIGNEE_NAME"),
                recon_user.c.USERNAME.label("ASSIGNEE_USERNAME"),
                recon_issue_reason.c.LABEL.label("REASON_LABEL"),
            )
            .outerjoin(recon_user, recon_issue.c.ASSIGNEE_ID == recon_user.c.ID)
            .outerjoin(recon_issue_reason, recon_issue.c.REASON_CODE == recon_issue_reason.c.CODE)
            .where(
                recon_issue.c.TEMPLATE_ID == run_row["TEMPLATE_ID"],
                recon_issue.c.PROFILE_CODE == run_row["PROFILE_CODE"],
                recon_issue.c.KEY_HASH == key_hash,
            )
        )
        issue_row = conn.execute(stmt).mappings().first()

    return dict(issue_row) if issue_row else None


@service
def upsert_issue_for_row(
    ctx: Ctx,
    run_id: int,
    row_no: int,
    reason_code: str | None = None,
    assignee_id: int | None = None,
    status: str = "OPEN",
    note: str | None = None,
) -> dict[str, Any]:
    """Tạo hoặc cập nhật xử lý chênh lệch cho một dòng kết quả cụ thể."""
    require_role(ctx, *MUTATION_ROLES)

    if status not in VALID_ISSUE_STATUSES:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Trạng thái '{status}' không hợp lệ. Phải là một trong: {', '.join(VALID_ISSUE_STATUSES)}.",
        )

    if reason_code is not None and not str(reason_code).strip():
        reason_code = None

    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        ensure_default_reasons(conn)

        run_row = (
            conn.execute(select(recon_run.c.TEMPLATE_ID, recon_run.c.PROFILE_CODE).where(recon_run.c.ID == run_id))
            .mappings()
            .first()
        )
        if not run_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy Run #{run_id}.")

        r_row = (
            conn.execute(
                select(recon_result_row.c.KEY_TEXT, recon_result_row.c.KEY_HASH).where(
                    recon_result_row.c.RUN_ID == run_id,
                    recon_result_row.c.ROW_NO == row_no,
                )
            )
            .mappings()
            .first()
        )
        if not r_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy dòng kết quả #{row_no} trong Run #{run_id}.")

        template_id = run_row["TEMPLATE_ID"]
        profile_code = run_row["PROFILE_CODE"]
        key_hash = r_row["KEY_HASH"]
        key_text = r_row["KEY_TEXT"]

        existing_issue = (
            conn.execute(
                select(recon_issue).where(
                    recon_issue.c.TEMPLATE_ID == template_id,
                    recon_issue.c.PROFILE_CODE == profile_code,
                    recon_issue.c.KEY_HASH == key_hash,
                )
            )
            .mappings()
            .first()
        )

        old_data = dict(existing_issue) if existing_issue else None

        if existing_issue:
            issue_id = int(existing_issue["ID"])
            conn.execute(
                update(recon_issue)
                .where(recon_issue.c.ID == issue_id)
                .values(
                    LAST_RUN_ID=run_id,
                    STATUS=status,
                    REASON_CODE=reason_code,
                    ASSIGNEE_ID=assignee_id,
                    NOTE=note,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=recon_issue.c.ROW_VERSION + 1,
                )
            )
            action = "UPDATE_ISSUE"
        else:
            ins = conn.execute(
                recon_issue.insert().values(
                    TEMPLATE_ID=template_id,
                    PROFILE_CODE=profile_code,
                    KEY_TEXT=key_text,
                    KEY_HASH=key_hash,
                    FIRST_RUN_ID=run_id,
                    LAST_RUN_ID=run_id,
                    STATUS=status,
                    REASON_CODE=reason_code,
                    ASSIGNEE_ID=assignee_id,
                    NOTE=note,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=1,
                )
            )
            issue_id = int(ins.inserted_primary_key[0]) if ins.inserted_primary_key else 1
            action = "CREATE_ISSUE"

        new_data = {
            "template_id": template_id,
            "profile_code": profile_code,
            "key_hash": key_hash,
            "status": status,
            "reason_code": reason_code,
            "assignee_id": assignee_id,
            "note": note,
        }

        write_audit_log(
            conn=conn,
            entity="ISSUE",
            entity_id=issue_id,
            action=action,
            actor=ctx.username,
            old_data=old_data,
            new_data=new_data,
            now=now,
        )

    return {
        "issue_id": issue_id,
        "action": action,
        "status": status,
        "key_hash": key_hash,
    }


@service
def bulk_upsert_issues(
    ctx: Ctx,
    run_id: int,
    row_nos: list[int],
    reason_code: str | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Cập nhật hoặc gán xử lý chênh lệch hàng loạt cho nhiều dòng trong run."""
    require_role(ctx, *MUTATION_ROLES)

    if not row_nos:
        return {"count": 0, "updated_issues": []}

    if status and status not in VALID_ISSUE_STATUSES:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Trạng thái '{status}' không hợp lệ. Phải là một trong: {', '.join(VALID_ISSUE_STATUSES)}.",
        )

    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        ensure_default_reasons(conn)

        run_row = (
            conn.execute(select(recon_run.c.TEMPLATE_ID, recon_run.c.PROFILE_CODE).where(recon_run.c.ID == run_id))
            .mappings()
            .first()
        )
        if not run_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy Run #{run_id}.")

        template_id = run_row["TEMPLATE_ID"]
        profile_code = run_row["PROFILE_CODE"]

        # Lấy toàn bộ các dòng kết quả theo lô
        res_rows = (
            conn.execute(
                select(recon_result_row.c.ROW_NO, recon_result_row.c.KEY_TEXT, recon_result_row.c.KEY_HASH).where(
                    recon_result_row.c.RUN_ID == run_id,
                    recon_result_row.c.ROW_NO.in_(row_nos),
                )
            )
            .mappings()
            .all()
        )

        if not res_rows:
            return {"count": 0, "updated_issues": []}

        key_hashes = [r["KEY_HASH"] for r in res_rows]
        key_text_by_hash = {r["KEY_HASH"]: r["KEY_TEXT"] for r in res_rows}

        # Tra cứu các issue hiện có
        existing_issues = (
            conn.execute(
                select(recon_issue).where(
                    recon_issue.c.TEMPLATE_ID == template_id,
                    recon_issue.c.PROFILE_CODE == profile_code,
                    recon_issue.c.KEY_HASH.in_(key_hashes),
                )
            )
            .mappings()
            .all()
        )

        existing_by_hash = {r["KEY_HASH"]: dict(r) for r in existing_issues}

        target_status = status or "OPEN"
        updated_ids: list[int] = []

        # Tách danh sách update và insert
        for kh in key_hashes:
            if kh in existing_by_hash:
                iss = existing_by_hash[kh]
                iss_id = int(iss["ID"])
                upd_values: dict[str, Any] = {
                    "LAST_RUN_ID": run_id,
                    "UPDATED_BY": ctx.username,
                    "UPDATED_AT": now,
                    "ROW_VERSION": recon_issue.c.ROW_VERSION + 1,
                }
                if status:
                    upd_values["STATUS"] = status
                if reason_code is not None:
                    upd_values["REASON_CODE"] = reason_code
                if assignee_id is not None:
                    upd_values["ASSIGNEE_ID"] = assignee_id
                if note is not None:
                    upd_values["NOTE"] = note

                conn.execute(update(recon_issue).where(recon_issue.c.ID == iss_id).values(**upd_values))
                updated_ids.append(iss_id)
            else:
                ins = conn.execute(
                    recon_issue.insert().values(
                        TEMPLATE_ID=template_id,
                        PROFILE_CODE=profile_code,
                        KEY_TEXT=key_text_by_hash[kh],
                        KEY_HASH=kh,
                        FIRST_RUN_ID=run_id,
                        LAST_RUN_ID=run_id,
                        STATUS=target_status,
                        REASON_CODE=reason_code,
                        ASSIGNEE_ID=assignee_id,
                        NOTE=note,
                        UPDATED_BY=ctx.username,
                        UPDATED_AT=now,
                        ROW_VERSION=1,
                    )
                )
                new_id = int(ins.inserted_primary_key[0]) if ins.inserted_primary_key else 1
                updated_ids.append(new_id)

        # Ghi một bản ghi audit log duy nhất cho thao tác hàng loạt
        write_audit_log(
            conn=conn,
            entity="ISSUE",
            entity_id=f"RUN_{run_id}_BULK",
            action="BULK_UPDATE_ISSUE",
            actor=ctx.username,
            new_data={
                "run_id": run_id,
                "count": len(updated_ids),
                "status": status,
                "reason_code": reason_code,
                "assignee_id": assignee_id,
            },
            now=now,
        )

    return {
        "count": len(updated_ids),
        "updated_issues": updated_ids,
    }


@service
def list_issues(
    ctx: Ctx,
    template_id: int | None = None,
    profile_code: str | None = None,
    status: str | None = None,
    assignee_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Danh sách các vấn đề chênh lệch phục vụ màn hình /issues."""
    require_role(ctx, *ALL_ROLES)
    engine = get_recon_engine()

    page = max(1, page)
    page_size = max(1, min(200, page_size))
    offset = (page - 1) * page_size

    with engine.connect() as conn:
        stmt = (
            select(
                recon_issue,
                recon_template.c.NAME.label("TEMPLATE_NAME"),
                recon_template.c.CODE.label("TEMPLATE_CODE"),
                recon_user.c.FULL_NAME.label("ASSIGNEE_NAME"),
                recon_user.c.USERNAME.label("ASSIGNEE_USERNAME"),
                recon_issue_reason.c.LABEL.label("REASON_LABEL"),
            )
            .outerjoin(recon_template, recon_issue.c.TEMPLATE_ID == recon_template.c.ID)
            .outerjoin(recon_user, recon_issue.c.ASSIGNEE_ID == recon_user.c.ID)
            .outerjoin(recon_issue_reason, recon_issue.c.REASON_CODE == recon_issue_reason.c.CODE)
        )

        count_stmt = select(func.count()).select_from(recon_issue)

        conditions = []
        if template_id:
            conditions.append(recon_issue.c.TEMPLATE_ID == template_id)
        if profile_code:
            conditions.append(recon_issue.c.PROFILE_CODE == profile_code)
        if status:
            conditions.append(recon_issue.c.STATUS == status)
        if assignee_id:
            conditions.append(recon_issue.c.ASSIGNEE_ID == assignee_id)
        if search:
            s_clean = f"%{search.strip()}%"
            conditions.append(
                or_(
                    recon_issue.c.KEY_TEXT.ilike(s_clean),
                    recon_issue.c.NOTE.ilike(s_clean),
                )
            )

        if conditions:
            for cond in conditions:
                stmt = stmt.where(cond)
                count_stmt = count_stmt.where(cond)

        total_count = conn.execute(count_stmt).scalar() or 0

        stmt = stmt.order_by(desc(recon_issue.c.UPDATED_AT)).offset(offset).limit(page_size)
        rows = conn.execute(stmt).mappings().all()

        # Thống kê KPI tổng thể
        kpi_counts: dict[str, int] = {st: 0 for st in VALID_ISSUE_STATUSES}
        kpi_stmt = select(recon_issue.c.STATUS, func.count()).group_by(recon_issue.c.STATUS)
        for st_val, c_val in conn.execute(kpi_stmt).fetchall():
            if st_val in kpi_counts:
                kpi_counts[st_val] = c_val

    return {
        "items": [dict(r) for r in rows],
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "kpis": {
            "total": sum(kpi_counts.values()),
            "open": kpi_counts.get("OPEN", 0),
            "in_progress": kpi_counts.get("IN_PROGRESS", 0),
            "resolved": kpi_counts.get("RESOLVED", 0),
            "accepted": kpi_counts.get("ACCEPTED", 0),
        },
    }
