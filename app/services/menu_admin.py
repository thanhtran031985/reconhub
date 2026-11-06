"""Service quản trị menu — task 20, spec 11 mục 7.2.

Admin chỉnh hiển thị menu (tên, nhóm, thứ tự, tạm ẩn kèm lý do) mà không
sửa code. Lưu một lần cho mọi thay đổi trong một transaction, khóa lạc quan
ROW_VERSION từng dòng, ghi audit từng thay đổi, tăng PERM_REVISION một lần
để quyền có hiệu lực trong tối đa 5 giây.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import Connection, func, select

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_app_setting, recon_menu, recon_menu_group, recon_role, recon_role_menu
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import bump_perm_revision, requires_menu

_MAX_REASON_LEN = 300


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MenuChange(BaseModel):
    """Một thay đổi hiển thị trong payload lưu (UI chỉ gửi dòng đã đổi)."""

    kind: Literal["menu", "group"]
    code: str
    label: str | None = None
    group: str | None = None
    order: int | None = Field(default=None, ge=0)
    hidden: bool | None = None
    hidden_reason: str | None = Field(default=None, max_length=_MAX_REASON_LEN)
    row_version: int | None = None


def _read_revision(conn: Connection) -> int:
    """Đọc PERM_REVISION trong transaction đang mở (không qua cache 1 giây)."""
    raw = conn.execute(
        select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "PERM_REVISION")
    ).scalar_one_or_none()
    try:
        return int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


def _role_counts(conn: Connection) -> dict[str, int]:
    """Số vai trò đang dùng có từng menu (Q8)."""
    rows = conn.execute(
        select(recon_role_menu.c.MENU_CODE, func.count(func.distinct(recon_role_menu.c.ROLE_ID)))
        .select_from(recon_role_menu.join(recon_role, recon_role_menu.c.ROLE_ID == recon_role.c.ID))
        .where(recon_role.c.IS_ACTIVE == "Y")
        .group_by(recon_role_menu.c.MENU_CODE)
    ).all()
    return {str(code): int(count) for code, count in rows}


def _load_tree(conn: Connection) -> tuple[list[Any], list[Any]]:
    groups = conn.execute(select(recon_menu_group)).mappings().all()
    menus = conn.execute(select(recon_menu)).mappings().all()
    groups = sorted(groups, key=lambda g: g["DISPLAY_ORDER"] or g["SOURCE_ORDER"])
    menus = sorted(menus, key=lambda m: m["DISPLAY_ORDER"] or m["SOURCE_ORDER"])
    return list(groups), list(menus)


def _menu_dict(row: Any, role_count: int) -> dict[str, Any]:
    return {
        "code": str(row["CODE"]),
        "label": str(row["DISPLAY_LABEL"] or row["SOURCE_LABEL"]),
        "source_label": str(row["SOURCE_LABEL"]),
        "path": str(row["PATH"]),
        "icon": str(row["ICON"] or ""),
        "group": str(row["DISPLAY_GROUP"] or row["SOURCE_GROUP"]),
        "source_group": str(row["SOURCE_GROUP"]),
        "order": int(row["DISPLAY_ORDER"] or row["SOURCE_ORDER"]),
        "source_order": int(row["SOURCE_ORDER"]),
        "is_hideable": row["IS_HIDEABLE"] == "Y",
        "is_hidden": row["IS_HIDDEN"] == "Y",
        "hidden_reason": row["HIDDEN_REASON"],
        "is_new": row["IS_NEW"] == "Y",
        "is_removed": row["IS_REMOVED"] == "Y",
        "row_version": int(row["ROW_VERSION"] or 1),
        "role_count": role_count,
        "changed": (
            row["DISPLAY_LABEL"] is not None or row["DISPLAY_GROUP"] is not None or row["DISPLAY_ORDER"] is not None
        ),
    }


def _group_dict(row: Any, menus: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "code": str(row["CODE"]),
        "label": str(row["DISPLAY_LABEL"] or row["SOURCE_LABEL"]),
        "source_label": str(row["SOURCE_LABEL"]),
        "order": int(row["DISPLAY_ORDER"] or row["SOURCE_ORDER"]),
        "source_order": int(row["SOURCE_ORDER"]),
        "is_removed": row["IS_REMOVED"] == "Y",
        "row_version": int(row["ROW_VERSION"] or 1),
        "changed": row["DISPLAY_LABEL"] is not None or row["DISPLAY_ORDER"] is not None,
        "menus": menus,
    }


def _tree_data(conn: Connection) -> dict[str, Any]:
    groups, menus = _load_tree(conn)
    counts = _role_counts(conn)
    by_group: dict[str, list[dict[str, Any]]] = {}
    for m in menus:
        by_group.setdefault(str(m["DISPLAY_GROUP"] or m["SOURCE_GROUP"]), []).append(
            _menu_dict(m, counts.get(str(m["CODE"]), 0))
        )
    return {
        "groups": [_group_dict(g, by_group.get(str(g["CODE"]), [])) for g in groups],
        "revision": _read_revision(conn),
    }


def _check_version(row: Any, change: MenuChange, what: str) -> None:
    current = int(row["ROW_VERSION"] or 1)
    if change.row_version is not None and int(change.row_version) != current:
        raise ServiceError(
            ErrorCode.STALE_DATA,
            f"{what} đã bị thay đổi bởi người khác, vui lòng tải lại rồi sửa tiếp.",
        )


@service
@requires_menu("menu_admin")
def list_menu_tree_admin(ctx: Ctx) -> dict[str, Any]:
    """Cây nhóm + menu cho màn /menus (kèm menu đã gỡ, vai trò đang bật)."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        return _tree_data(conn)


@service
@requires_menu("menu_admin")
def save_menu_changes(ctx: Ctx, changes: list[dict[str, Any]]) -> dict[str, Any]:
    """Lưu một lần cho mọi thay đổi hiển thị (tên/nhóm/thứ tự/ẩn).

    Kiểm tra hết mọi thay đổi trước rồi mới ghi, trong một transaction:
    sai một dòng thì không ghi dòng nào. Tăng PERM_REVISION một lần.
    """
    parsed = [MenuChange.model_validate(c) for c in (changes or [])]
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        groups, menus = _load_tree(conn)
        group_by_code = {str(g["CODE"]): g for g in groups}
        menu_by_code = {str(m["CODE"]): m for m in menus}

        # Nhãn hiển thị cuối cùng sau khi áp mọi thay đổi (kiểm tra trùng
        # trên trạng thái cuối, kể cả hai menu đổi tên cho nhau).
        final_labels = {
            code: str(m["DISPLAY_LABEL"] or m["SOURCE_LABEL"]).strip().lower()
            for code, m in menu_by_code.items()
            if m["IS_REMOVED"] != "Y"
        }
        for ch in parsed:
            if ch.kind == "menu" and ch.label is not None:
                final_labels[ch.code] = ch.label.strip().lower()
        seen: dict[str, str] = {}
        for code, label in final_labels.items():
            if label in seen:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Tên hiển thị '{label}' trùng với menu khác.",
                )
            seen[label] = code

        applied: list[dict[str, Any]] = []
        for ch in parsed:
            if ch.kind == "group":
                applied.extend(_apply_group_change(conn, group_by_code, ch, ctx, now))
            else:
                applied.extend(_apply_menu_change(conn, menu_by_code, group_by_code, ch, ctx, now))
        revision = _read_revision(conn)
        if applied:
            revision = bump_perm_revision(conn, ctx.username)
        return {"applied": applied, "revision": revision}


def _apply_group_change(
    conn: Connection,
    group_by_code: dict[str, Any],
    ch: MenuChange,
    ctx: Ctx,
    now: datetime,
) -> list[dict[str, Any]]:
    row = group_by_code.get(ch.code)
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy nhóm menu '{ch.code}'.")
    if row["IS_REMOVED"] == "Y":
        raise ServiceError(ErrorCode.MENU_REMOVED, f"Nhóm menu '{ch.code}' đã bị gỡ khỏi hệ thống.")
    _check_version(row, ch, f"Nhóm menu '{ch.code}'")
    old = {
        "label": str(row["DISPLAY_LABEL"] or row["SOURCE_LABEL"]),
        "order": int(row["DISPLAY_ORDER"] or row["SOURCE_ORDER"]),
    }
    new_label = old["label"]
    if ch.label is not None:
        if not ch.label.strip():
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Tên nhóm không được để trống.")
        new_label = ch.label.strip()
    new_order = old["order"] if ch.order is None else int(ch.order)
    if new_label == old["label"] and new_order == old["order"]:
        return []
    values: dict[str, Any] = {
        "DISPLAY_LABEL": None if new_label == str(row["SOURCE_LABEL"]) else new_label,
        "DISPLAY_ORDER": None if new_order == int(row["SOURCE_ORDER"]) else new_order,
        "UPDATED_BY": ctx.username,
        "UPDATED_AT": now,
        "ROW_VERSION": int(row["ROW_VERSION"] or 1) + 1,
    }
    conn.execute(recon_menu_group.update().where(recon_menu_group.c.CODE == ch.code).values(**values))
    write_audit_log(
        conn=conn,
        entity="RECON_MENU_GROUP",
        entity_id=ch.code,
        action="UPDATE_MENU_GROUP",
        actor=ctx.username,
        old_data={"label": old["label"], "order": old["order"]},
        new_data={"label": new_label, "order": new_order},
        now=now,
    )
    fields = []
    if new_label != old["label"]:
        fields.append("label")
    if new_order != old["order"]:
        fields.append("order")
    return [{"kind": "group", "code": ch.code, "fields": fields}]


def _apply_menu_change(
    conn: Connection,
    menu_by_code: dict[str, Any],
    group_by_code: dict[str, Any],
    ch: MenuChange,
    ctx: Ctx,
    now: datetime,
) -> list[dict[str, Any]]:
    row = menu_by_code.get(ch.code)
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy menu '{ch.code}'.")
    if row["IS_REMOVED"] == "Y":
        raise ServiceError(ErrorCode.MENU_REMOVED, f"Menu '{ch.code}' đã bị gỡ khỏi hệ thống.")
    _check_version(row, ch, f"Menu '{ch.code}'")
    old = {
        "label": str(row["DISPLAY_LABEL"] or row["SOURCE_LABEL"]),
        "group": str(row["DISPLAY_GROUP"] or row["SOURCE_GROUP"]),
        "order": int(row["DISPLAY_ORDER"] or row["SOURCE_ORDER"]),
        "hidden": row["IS_HIDDEN"] == "Y",
        "hidden_reason": row["HIDDEN_REASON"],
    }
    new_label = old["label"]
    if ch.label is not None:
        if not ch.label.strip():
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Tên hiển thị không được để trống.")
        new_label = ch.label.strip()
    new_group = old["group"]
    if ch.group is not None:
        target = group_by_code.get(ch.group)
        if target is None or target["IS_REMOVED"] == "Y":
            raise ServiceError(ErrorCode.MENU_GROUP_INVALID, f"Nhóm menu '{ch.group}' không tồn tại.")
        new_group = ch.group
    new_order = old["order"]
    if ch.order is not None:
        new_order = int(ch.order)
    elif new_group != old["group"]:
        # Đổi nhóm: menu xuống cuối nhóm mới.
        siblings = [
            int(m["DISPLAY_ORDER"] or m["SOURCE_ORDER"])
            for m in menu_by_code.values()
            if str(m["DISPLAY_GROUP"] or m["SOURCE_GROUP"]) == new_group
            and str(m["CODE"]) != ch.code
            and m["IS_REMOVED"] != "Y"
        ]
        new_order = (max(siblings) if siblings else 0) + 10
    new_hidden = old["hidden"] if ch.hidden is None else bool(ch.hidden)
    new_reason = old["hidden_reason"]
    if new_hidden and not old["hidden"]:
        if row["IS_HIDEABLE"] != "Y":
            raise ServiceError(
                ErrorCode.MENU_NOT_HIDEABLE,
                f"Menu '{ch.code}' là menu bắt buộc của quản trị, không ẩn được.",
            )
        reason = (ch.hidden_reason or "").strip() or (old["hidden_reason"] or "").strip()
        if not reason:
            raise ServiceError(
                ErrorCode.MENU_HIDE_REASON_REQUIRED,
                "Ẩn menu phải nhập lý do (hiển thị cho người dùng ở trang tạm ngưng).",
            )
        new_reason = reason
    if not new_hidden:
        new_reason = None
    if (
        new_label == old["label"]
        and new_group == old["group"]
        and new_order == old["order"]
        and new_hidden == old["hidden"]
        and (new_reason or None) == (old["hidden_reason"] or None)
    ):
        return []
    values: dict[str, Any] = {
        "DISPLAY_LABEL": None if new_label == str(row["SOURCE_LABEL"]) else new_label,
        "DISPLAY_GROUP": None if new_group == str(row["SOURCE_GROUP"]) else new_group,
        "DISPLAY_ORDER": None if new_order == int(row["SOURCE_ORDER"]) else new_order,
        "IS_HIDDEN": "Y" if new_hidden else "N",
        "HIDDEN_REASON": new_reason,
        "HIDDEN_BY": ctx.username if new_hidden else None,
        "HIDDEN_AT": now if new_hidden else None,
        "UPDATED_BY": ctx.username,
        "UPDATED_AT": now,
        "ROW_VERSION": int(row["ROW_VERSION"] or 1) + 1,
    }
    conn.execute(recon_menu.update().where(recon_menu.c.CODE == ch.code).values(**values))
    action = "UPDATE_MENU"
    if new_hidden and not old["hidden"]:
        action = "HIDE_MENU"
    elif old["hidden"] and not new_hidden:
        action = "UNHIDE_MENU"
    write_audit_log(
        conn=conn,
        entity="RECON_MENU",
        entity_id=ch.code,
        action=action,
        actor=ctx.username,
        old_data={
            "label": old["label"],
            "group": old["group"],
            "order": old["order"],
            "hidden": old["hidden"],
            "hidden_reason": old["hidden_reason"],
        },
        new_data={
            "label": new_label,
            "group": new_group,
            "order": new_order,
            "hidden": new_hidden,
            "hidden_reason": new_reason,
        },
        now=now,
    )
    fields = []
    if new_label != old["label"]:
        fields.append("label")
    if new_group != old["group"]:
        fields.append("group")
    if new_order != old["order"]:
        fields.append("order")
    if new_hidden != old["hidden"]:
        fields.append("hidden")
    return [{"kind": "menu", "code": ch.code, "fields": fields}]


@service
@requires_menu("menu_admin")
def reset_menus(ctx: Ctx, code: str, row_version: int | None = None) -> dict[str, Any]:
    """Khôi phục mặc định (DISPLAY_* về NULL) cho một menu/nhóm hoặc tất cả.

    Không đổi trạng thái ẩn, không đổi phân quyền vai trò.
    """
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        groups, menus = _load_tree(conn)
        reset_codes: list[str] = []
        if code == "ALL":
            for m in menus:
                if m["IS_REMOVED"] == "Y":
                    continue
                if m["DISPLAY_LABEL"] is not None or m["DISPLAY_GROUP"] is not None or m["DISPLAY_ORDER"] is not None:
                    conn.execute(
                        recon_menu.update()
                        .where(recon_menu.c.CODE == m["CODE"])
                        .values(
                            DISPLAY_LABEL=None,
                            DISPLAY_GROUP=None,
                            DISPLAY_ORDER=None,
                            UPDATED_BY=ctx.username,
                            UPDATED_AT=now,
                            ROW_VERSION=int(m["ROW_VERSION"] or 1) + 1,
                        )
                    )
                    write_audit_log(
                        conn=conn,
                        entity="RECON_MENU",
                        entity_id=str(m["CODE"]),
                        action="RESET_MENU",
                        actor=ctx.username,
                        old_data={"label": str(m["DISPLAY_LABEL"] or m["SOURCE_LABEL"])},
                        new_data={"label": str(m["SOURCE_LABEL"])},
                        now=now,
                    )
                    reset_codes.append(str(m["CODE"]))
            for g in groups:
                if g["IS_REMOVED"] == "Y":
                    continue
                if g["DISPLAY_LABEL"] is not None or g["DISPLAY_ORDER"] is not None:
                    conn.execute(
                        recon_menu_group.update()
                        .where(recon_menu_group.c.CODE == g["CODE"])
                        .values(
                            DISPLAY_LABEL=None,
                            DISPLAY_ORDER=None,
                            UPDATED_BY=ctx.username,
                            UPDATED_AT=now,
                            ROW_VERSION=int(g["ROW_VERSION"] or 1) + 1,
                        )
                    )
                    write_audit_log(
                        conn=conn,
                        entity="RECON_MENU_GROUP",
                        entity_id=str(g["CODE"]),
                        action="RESET_MENU_GROUP",
                        actor=ctx.username,
                        old_data={"label": str(g["DISPLAY_LABEL"] or g["SOURCE_LABEL"])},
                        new_data={"label": str(g["SOURCE_LABEL"])},
                        now=now,
                    )
                    reset_codes.append(str(g["CODE"]))
        else:
            menu_row = next((m for m in menus if str(m["CODE"]) == code), None)
            group_row = next((g for g in groups if str(g["CODE"]) == code), None)
            if menu_row is not None:
                _check_version(menu_row, MenuChange(kind="menu", code=code, row_version=row_version), f"Menu '{code}'")
                if (
                    menu_row["DISPLAY_LABEL"] is not None
                    or menu_row["DISPLAY_GROUP"] is not None
                    or menu_row["DISPLAY_ORDER"] is not None
                ):
                    conn.execute(
                        recon_menu.update()
                        .where(recon_menu.c.CODE == code)
                        .values(
                            DISPLAY_LABEL=None,
                            DISPLAY_GROUP=None,
                            DISPLAY_ORDER=None,
                            UPDATED_BY=ctx.username,
                            UPDATED_AT=now,
                            ROW_VERSION=int(menu_row["ROW_VERSION"] or 1) + 1,
                        )
                    )
                    write_audit_log(
                        conn=conn,
                        entity="RECON_MENU",
                        entity_id=code,
                        action="RESET_MENU",
                        actor=ctx.username,
                        old_data={"label": str(menu_row["DISPLAY_LABEL"] or menu_row["SOURCE_LABEL"])},
                        new_data={"label": str(menu_row["SOURCE_LABEL"])},
                        now=now,
                    )
                    reset_codes.append(code)
            elif group_row is not None:
                _check_version(
                    group_row, MenuChange(kind="group", code=code, row_version=row_version), f"Nhóm menu '{code}'"
                )
                if group_row["DISPLAY_LABEL"] is not None or group_row["DISPLAY_ORDER"] is not None:
                    conn.execute(
                        recon_menu_group.update()
                        .where(recon_menu_group.c.CODE == code)
                        .values(
                            DISPLAY_LABEL=None,
                            DISPLAY_ORDER=None,
                            UPDATED_BY=ctx.username,
                            UPDATED_AT=now,
                            ROW_VERSION=int(group_row["ROW_VERSION"] or 1) + 1,
                        )
                    )
                    write_audit_log(
                        conn=conn,
                        entity="RECON_MENU_GROUP",
                        entity_id=code,
                        action="RESET_MENU_GROUP",
                        actor=ctx.username,
                        old_data={"label": str(group_row["DISPLAY_LABEL"] or group_row["SOURCE_LABEL"])},
                        new_data={"label": str(group_row["SOURCE_LABEL"])},
                        now=now,
                    )
                    reset_codes.append(code)
            else:
                raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy menu hoặc nhóm '{code}'.")
        revision = _read_revision(conn)
        if reset_codes:
            revision = bump_perm_revision(conn, ctx.username)
        return {"reset": reset_codes, "revision": revision}


@service
@requires_menu("menu_admin")
def mark_seen(ctx: Ctx, code: str) -> dict[str, Any]:
    """Đánh dấu đã xem menu mới (bỏ nhãn Mới), một menu hoặc tất cả (Q1)."""
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        _, menus = _load_tree(conn)
        if code == "ALL":
            targets = [m for m in menus if m["IS_NEW"] == "Y"]
        else:
            row = next((m for m in menus if str(m["CODE"]) == code), None)
            if row is None:
                raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy menu '{code}'.")
            targets = [row] if row["IS_NEW"] == "Y" else []
        for m in targets:
            conn.execute(
                recon_menu.update()
                .where(recon_menu.c.CODE == m["CODE"])
                .values(IS_NEW="N", UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
        revision = _read_revision(conn)
        if targets:
            revision = bump_perm_revision(conn, ctx.username)
        return {"marked": [str(m["CODE"]) for m in targets], "revision": revision}


@service
@requires_menu("menu_admin")
def preview_sidebar(ctx: Ctx, changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Xem trước thanh bên theo thay đổi chưa lưu (áp trong bộ nhớ).

    Menu đang ẩn không hiện; menu đã gỡ không hiện; nhóm không còn menu nào
    thì ẩn. Theo prototype Screen15: hiện đủ mọi menu chưa ẩn (kể cả menu
    quản trị), không lọc theo vai trò.
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        groups, menus = _load_tree(conn)
    # Áp thay đổi trong bộ nhớ, bỏ qua dòng không hợp lệ (chỉ xem trước).
    by_code: dict[str, dict[str, Any]] = {}
    for m in menus:
        by_code[str(m["CODE"])] = {
            "code": str(m["CODE"]),
            "label": str(m["DISPLAY_LABEL"] or m["SOURCE_LABEL"]),
            "group": str(m["DISPLAY_GROUP"] or m["SOURCE_GROUP"]),
            "order": int(m["DISPLAY_ORDER"] or m["SOURCE_ORDER"]),
            "path": str(m["PATH"]),
            "icon": str(m["ICON"] or ""),
            "hidden": m["IS_HIDDEN"] == "Y",
            "removed": m["IS_REMOVED"] == "Y",
        }
    group_labels: dict[str, str] = {}
    group_orders: dict[str, int] = {}
    for g in groups:
        group_labels[str(g["CODE"])] = str(g["DISPLAY_LABEL"] or g["SOURCE_LABEL"])
        group_orders[str(g["CODE"])] = int(g["DISPLAY_ORDER"] or g["SOURCE_ORDER"])
    for raw in changes or []:
        try:
            ch = MenuChange.model_validate(raw)
        except Exception:
            continue
        if ch.kind == "group":
            if ch.code in group_labels:
                if ch.label is not None and ch.label.strip():
                    group_labels[ch.code] = ch.label.strip()
                if ch.order is not None:
                    group_orders[ch.code] = int(ch.order)
            continue
        item = by_code.get(ch.code)
        if item is None or item["removed"]:
            continue
        if ch.label is not None and ch.label.strip():
            item["label"] = ch.label.strip()
        if ch.group is not None and ch.group in group_labels:
            item["group"] = ch.group
        if ch.order is not None:
            item["order"] = int(ch.order)
        if ch.hidden is not None:
            item["hidden"] = bool(ch.hidden)
    nav: list[dict[str, Any]] = []
    for code in sorted(group_labels, key=lambda c: group_orders.get(c, 0)):
        items = [
            {"label": m["label"], "href": m["path"], "icon": m["icon"]}
            for m in sorted(by_code.values(), key=lambda m: (m["order"], m["code"]))
            if m["group"] == code and not m["hidden"] and not m["removed"]
        ]
        if items:
            nav.append({"title": group_labels[code].upper(), "items": items})
    return nav
