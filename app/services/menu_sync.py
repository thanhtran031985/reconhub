"""Đồng bộ danh sách menu trong code vào DB khi khởi động (task 19).

Quy tắc (spec 11 mục 2.2):
- Menu mới trong code → thêm vào DB, IS_NEW='Y', không gán cho vai trò nào.
- Menu đổi label/đường dẫn/nhóm/thứ tự trong code → cập nhật trường
  SOURCE_*; không ghi đè DISPLAY_* của Admin.
- Menu biến mất khỏi code → IS_REMOVED='Y', giữ cấu hình; xuất hiện
  lại → khôi phục IS_REMOVED='N' cùng cấu hình cũ.
- Đồng bộ được gọi từ 2 process cùng lúc thì không chạy chồng: khóa
  bằng RECON_APP_SETTING.MENU_SYNC_LOCK (giữ tối đa 60 giây).
- Có thay đổi thì tăng PERM_REVISION và ghi audit (actor system).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_app_setting, recon_menu, recon_menu_group
from app.services import service
from app.services.perm import requires_menu
from app.ui import menus as menus_mod

_LOCK_TTL = timedelta(seconds=60)
_LOCK_KEY = "MENU_SYNC_LOCK"
_REVISION_KEY = "PERM_REVISION"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_lock(value: str | None) -> datetime | None:
    if not value or value == "N":
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def sync_from_code(engine: Engine | None = None) -> dict[str, Any]:
    """Đồng bộ menu từ code vào DB. Trả về tóm tắt thay đổi."""
    engine = engine or get_recon_engine()
    now = _now()

    from sqlalchemy import inspect as _inspect

    if "RECON_MENU" not in _inspect(engine).get_table_names():
        return {"changed": False, "skipped": True, "reason": "tables-missing"}

    # Giữ khóa trong transaction riêng: process nào thua cuộc đua insert
    # (UNIQUE constraint) thì bỏ qua, process thắng sẽ đồng bộ xong và
    # việc đồng bộ là idempotent nên bỏ qua là an toàn.
    try:
        with engine.begin() as conn:
            lock_row = conn.execute(
                select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == _LOCK_KEY)
            ).scalar_one_or_none()
            held_at = _parse_lock(lock_row)
            if held_at is not None and now - held_at < _LOCK_TTL:
                return {"changed": False, "skipped": True, "reason": "locked"}
            if lock_row is None:
                conn.execute(
                    recon_app_setting.insert().values(
                        KEY=_LOCK_KEY, VALUE=now.isoformat(), UPDATED_BY="system", UPDATED_AT=now
                    )
                )
            else:
                conn.execute(
                    recon_app_setting.update()
                    .where(recon_app_setting.c.KEY == _LOCK_KEY)
                    .values(VALUE=now.isoformat(), UPDATED_BY="system", UPDATED_AT=now)
                )
    except SQLAlchemyError:
        return {"changed": False, "skipped": True, "reason": "locked"}

    try:
        result = _sync_locked(engine, now)
    finally:
        # Luôn trả khóa, kể cả khi đồng bộ lỗi (khóa hết hạn sau 60 giây
        # nếu process chết trước khi trả).
        try:
            with engine.begin() as conn:
                conn.execute(
                    recon_app_setting.update()
                    .where(recon_app_setting.c.KEY == _LOCK_KEY)
                    .values(VALUE="N", UPDATED_BY="system", UPDATED_AT=_now())
                )
        except SQLAlchemyError:
            pass
    return result


def _sync_locked(engine: Engine, now: datetime) -> dict[str, Any]:
    """Phần đồng bộ thật, chạy sau khi đã giữ khóa."""
    with engine.begin() as conn:
        added = 0
        added_menus = 0
        added_groups = 0
        updated = 0
        removed = 0
        restored = 0

        code_groups = {g.code: g for g in menus_mod.GROUPS}
        db_groups = {row["CODE"]: row for row in conn.execute(select(recon_menu_group)).mappings().all()}
        for group in menus_mod.GROUPS:
            row = db_groups.get(group.code)
            if row is None:
                conn.execute(
                    recon_menu_group.insert().values(
                        CODE=group.code,
                        SOURCE_LABEL=group.label,
                        SOURCE_ORDER=group.order,
                        DISPLAY_LABEL=None,
                        DISPLAY_ORDER=None,
                        IS_REMOVED="N",
                        SYNCED_AT=now,
                        UPDATED_BY="system",
                        UPDATED_AT=now,
                        ROW_VERSION=1,
                    )
                )
                added += 1
                added_groups += 1
            elif row["SOURCE_LABEL"] != group.label or row["SOURCE_ORDER"] != group.order or row["IS_REMOVED"] == "Y":
                conn.execute(
                    recon_menu_group.update()
                    .where(recon_menu_group.c.CODE == group.code)
                    .values(
                        SOURCE_LABEL=group.label,
                        SOURCE_ORDER=group.order,
                        IS_REMOVED="N",
                        SYNCED_AT=now,
                        UPDATED_BY="system",
                        UPDATED_AT=now,
                        ROW_VERSION=recon_menu_group.c.ROW_VERSION + 1,
                    )
                )
                updated += 1
        for code, row in db_groups.items():
            if code not in code_groups and row["IS_REMOVED"] != "Y":
                conn.execute(
                    recon_menu_group.update()
                    .where(recon_menu_group.c.CODE == code)
                    .values(IS_REMOVED="Y", SYNCED_AT=now, UPDATED_BY="system", UPDATED_AT=now)
                )
                removed += 1

        db_menus = {row["CODE"]: row for row in conn.execute(select(recon_menu)).mappings().all()}
        for menu in menus_mod.MENUS:
            row = db_menus.get(menu.code)
            if row is None:
                conn.execute(
                    recon_menu.insert().values(
                        CODE=menu.code,
                        PATH=menu.path,
                        ICON=menu.icon,
                        SOURCE_LABEL=menu.label,
                        SOURCE_GROUP=menu.group,
                        SOURCE_ORDER=menu.order,
                        DISPLAY_LABEL=None,
                        DISPLAY_GROUP=None,
                        DISPLAY_ORDER=None,
                        IS_HIDEABLE=menu.hideable,
                        IS_HIDDEN="N",
                        HIDDEN_REASON=None,
                        HIDDEN_BY=None,
                        HIDDEN_AT=None,
                        IS_NEW="Y",
                        IS_REMOVED="N",
                        SYNCED_AT=now,
                        UPDATED_BY="system",
                        UPDATED_AT=now,
                        ROW_VERSION=1,
                    )
                )
                added += 1
                added_menus += 1
            elif (
                row["SOURCE_LABEL"] != menu.label
                or row["SOURCE_GROUP"] != menu.group
                or row["SOURCE_ORDER"] != menu.order
                or row["PATH"] != menu.path
                or (row["ICON"] or "") != (menu.icon or "")
                or row["IS_HIDEABLE"] != menu.hideable
                or row["IS_REMOVED"] == "Y"
            ):
                was_removed = row["IS_REMOVED"] == "Y"
                conn.execute(
                    recon_menu.update()
                    .where(recon_menu.c.CODE == menu.code)
                    .values(
                        PATH=menu.path,
                        ICON=menu.icon,
                        SOURCE_LABEL=menu.label,
                        SOURCE_GROUP=menu.group,
                        SOURCE_ORDER=menu.order,
                        IS_HIDEABLE=menu.hideable,
                        IS_REMOVED="N",
                        SYNCED_AT=now,
                        UPDATED_BY="system",
                        UPDATED_AT=now,
                        ROW_VERSION=recon_menu.c.ROW_VERSION + 1,
                    )
                )
                if was_removed:
                    restored += 1
                else:
                    updated += 1
        code_menu_codes = {m.code for m in menus_mod.MENUS}
        for code, row in db_menus.items():
            if code not in code_menu_codes and row["IS_REMOVED"] != "Y":
                conn.execute(
                    recon_menu.update()
                    .where(recon_menu.c.CODE == code)
                    .values(IS_REMOVED="Y", SYNCED_AT=now, UPDATED_BY="system", UPDATED_AT=now)
                )
                removed += 1

        changed = added > 0 or updated > 0 or removed > 0 or restored > 0
        revision = None
        if changed:
            rev_row = conn.execute(
                select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == _REVISION_KEY)
            ).scalar_one_or_none()
            try:
                revision = int(rev_row) + 1 if rev_row is not None else 1
            except (TypeError, ValueError):
                revision = 1
            if rev_row is None:
                conn.execute(
                    recon_app_setting.insert().values(
                        KEY=_REVISION_KEY,
                        VALUE=str(revision),
                        UPDATED_BY="system",
                        UPDATED_AT=now,
                    )
                )
            else:
                conn.execute(
                    recon_app_setting.update()
                    .where(recon_app_setting.c.KEY == _REVISION_KEY)
                    .values(VALUE=str(revision), UPDATED_BY="system", UPDATED_AT=now)
                )
            write_audit_log(
                conn=conn,
                entity="MENU",
                entity_id="SYNC",
                action="MENU_SYNC",
                actor="system",
                new_data={
                    "added": added,
                    "updated": updated,
                    "removed": removed,
                    "restored": restored,
                    "revision": revision,
                },
                now=now,
            )

        return {
            "changed": changed,
            "skipped": False,
            "added": added,
            "added_menus": added_menus,
            "added_groups": added_groups,
            "updated": updated,
            "removed": removed,
            "restored": restored,
            "revision": revision,
        }


@service
@requires_menu("role")
def list_menu_tree(ctx: Ctx) -> list[dict[str, Any]]:
    """Cây menu theo nhóm (tên hiển thị, thứ tự, trạng thái) cho trang /roles.

    Menu đã gỡ khỏi code không trả về; menu mới/đang ẩn vẫn trả về kèm cờ
    để giao diện gắn nhãn.
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        groups = conn.execute(select(recon_menu_group)).mappings().all()
        menus = conn.execute(select(recon_menu)).mappings().all()
    groups = sorted(groups, key=lambda g: g["DISPLAY_ORDER"] or g["SOURCE_ORDER"])
    menus = sorted(menus, key=lambda m: m["DISPLAY_ORDER"] or m["SOURCE_ORDER"])
    by_group: dict[str, list[dict[str, Any]]] = {}
    for m in menus:
        if m["IS_REMOVED"] == "Y":
            continue
        by_group.setdefault(str(m["DISPLAY_GROUP"] or m["SOURCE_GROUP"]), []).append(
            {
                "code": str(m["CODE"]),
                "label": str(m["DISPLAY_LABEL"] or m["SOURCE_LABEL"]),
                "path": str(m["PATH"]),
                "icon": str(m["ICON"]),
                "is_new": m["IS_NEW"] == "Y",
                "is_hidden": m["IS_HIDDEN"] == "Y",
            }
        )
    tree = []
    for g in groups:
        items = by_group.get(str(g["CODE"]), [])
        if items:
            tree.append(
                {
                    "code": str(g["CODE"]),
                    "label": str(g["DISPLAY_LABEL"] or g["SOURCE_LABEL"]),
                    "menus": items,
                }
            )
    return tree


def sync_menus_safely(engine: Engine | None = None) -> dict[str, Any]:
    """Gọi từ khởi động web: đồng bộ menu nhưng không làm sập app nếu lỗi."""
    try:
        return sync_from_code(engine)
    except (SQLAlchemyError, ValueError, KeyError):
        return {"changed": False, "skipped": True, "reason": "error"}
