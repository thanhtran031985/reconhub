"""app/ui/pages/menus.py — Màn hình Danh sách menu (Screen15).

Theo spec 11 mục 4.1/4.3/6/7.2/8/9 và task 20 bước 4: ADMIN chỉnh hiển
thị menu mà không sửa code — đổi tên hiển thị, chuyển nhóm, sắp xếp
thứ tự (nút ↑↓), tạm ẩn menu (bắt buộc có lý do), khôi phục mặc định,
đánh dấu menu mới đã xem. Mọi sửa đổi chỉ nằm ở bản nháp cho tới khi
bấm Lưu; Lưu gọi menu_admin.save_menu_changes trong một giao dịch
(kèm kiểm tra row_version từng dòng) rồi gọi mark_seen cho các menu
bỏ nhãn Mới. Chỉ ADMIN truy cập (menu `menu_admin`).
"""

from __future__ import annotations

import copy
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, clientside_callback, dcc, html
from dash_iconify import DashIconify

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.services.menu_admin import list_menu_tree_admin, mark_seen, preview_sidebar, save_menu_changes
from app.services.perm import is_admin, page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.page_header import page_header

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/menus",
        title="Danh sách menu — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "menu_admin"

# Mã menu chỉ ADMIN mới có (không gán cho vai trò thường): hiển thị chip "Admin".
_ADMIN_ONLY_CODES = {"user", "role", "menu_admin"}

_FILTER_OPTIONS = [
    {"label": "Tất cả", "value": "all"},
    {"label": "Đang ẩn", "value": "hidden"},
    {"label": "Mới", "value": "new"},
    {"label": "Đã đổi so với mặc định", "value": "changed"},
    {"label": "Đã gỡ khỏi code", "value": "removed"},
]


def _ctx_or_none() -> Ctx | None:
    return get_current_ctx()


# ---------- Helper thuần (dễ test) ----------


def _menu_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {m["code"]: m for g in tree.get("groups", []) for m in g.get("menus", [])}


def _group_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {g["code"]: g for g in tree.get("groups", [])}


def _menu_changed(saved_menu: dict[str, Any], draft_menu: dict[str, Any]) -> bool:
    for key in ("label", "group", "order", "is_hidden", "hidden_reason"):
        if saved_menu.get(key) != draft_menu.get(key):
            return True
    return False


def _group_changed(saved_group: dict[str, Any], draft_group: dict[str, Any]) -> bool:
    return saved_group.get("label") != draft_group.get("label") or saved_group.get("order") != draft_group.get("order")


def diff_changes(saved: dict[str, Any], draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Diff bản nháp so với bản đã lưu, đúng payload của save_menu_changes.

    Nhãn Mới (is_new) không nằm trong payload lưu — Lưu xong sẽ gọi
    mark_seen riêng cho các menu bỏ nhãn Mới (xem new_flips).
    """
    changes: list[dict[str, Any]] = []
    saved_menus = _menu_index(saved)
    saved_groups = _group_index(saved)
    for group in draft.get("groups", []):
        sg = saved_groups.get(group["code"])
        if sg is not None and _group_changed(sg, group):
            change: dict[str, Any] = {"kind": "group", "code": group["code"], "row_version": sg["row_version"]}
            if group["label"] != sg["label"]:
                change["label"] = group["label"]
            if group["order"] != sg["order"]:
                change["order"] = group["order"]
            changes.append(change)
        for menu in group.get("menus", []):
            sm = saved_menus.get(menu["code"])
            if sm is None or not _menu_changed(sm, menu):
                continue
            change = {"kind": "menu", "code": menu["code"], "row_version": sm["row_version"]}
            if menu["label"] != sm["label"]:
                change["label"] = menu["label"]
            if menu["group"] != sm["group"]:
                change["group"] = menu["group"]
            if menu["order"] != sm["order"]:
                change["order"] = menu["order"]
            if menu["is_hidden"] != sm["is_hidden"]:
                change["hidden"] = menu["is_hidden"]
                if menu["is_hidden"]:
                    change["hidden_reason"] = menu["hidden_reason"]
            elif menu["is_hidden"] and menu["hidden_reason"] != sm["hidden_reason"]:
                change["hidden"] = True
                change["hidden_reason"] = menu["hidden_reason"]
            changes.append(change)
    return changes


def new_flips(saved: dict[str, Any], draft: dict[str, Any]) -> list[str]:
    """Mã các menu bỏ nhãn Mới trong bản nháp (is_new True -> False)."""
    saved_menus = _menu_index(saved)
    flips: list[str] = []
    for code, menu in _menu_index(draft).items():
        sm = saved_menus.get(code)
        if sm is not None and sm.get("is_new") and not menu.get("is_new"):
            flips.append(code)
    return flips


def describe_changes(saved: dict[str, Any], draft: dict[str, Any]) -> list[str]:
    """Mô tả từng thay đổi bằng tiếng Việt cho hộp thoại Lưu."""
    lines: list[str] = []
    saved_menus = _menu_index(saved)
    saved_groups = _group_index(saved)
    for group in draft.get("groups", []):
        sg = saved_groups.get(group["code"])
        if sg is not None and _group_changed(sg, group):
            if group["label"] != sg["label"]:
                lines.append(f"Nhóm “{sg['label']}”: tên “{sg['label']}” → “{group['label']}”")
            if group["order"] != sg["order"]:
                lines.append(f"Nhóm “{group['label']}”: đổi thứ tự {sg['order']} → {group['order']}")
        for menu in group.get("menus", []):
            sm = saved_menus.get(menu["code"])
            if sm is None or not _menu_changed(sm, menu):
                continue
            label = sm["label"]
            if menu["label"] != sm["label"]:
                lines.append(f"Menu “{label}”: tên “{sm['label']}” → “{menu['label']}”")
            if menu["group"] != sm["group"]:
                new_group = _group_index(draft).get(menu["group"], {}).get("label", menu["group"])
                lines.append(f"Menu “{label}”: chuyển nhóm → “{new_group}”")
            if menu["order"] != sm["order"]:
                lines.append(f"Menu “{label}”: đổi thứ tự {sm['order']} → {menu['order']}")
            if menu["is_hidden"] != sm["is_hidden"]:
                if menu["is_hidden"]:
                    lines.append(f"Menu “{label}”: tạm ẩn (lý do: {menu['hidden_reason']})")
                else:
                    lines.append(f"Menu “{label}”: bỏ ẩn")
            elif menu["is_hidden"] and menu["hidden_reason"] != sm["hidden_reason"]:
                lines.append(f"Menu “{label}”: đổi lý do ẩn → {menu['hidden_reason']}")
    for code in new_flips(saved, draft):
        menu = _menu_index(draft).get(code, {})
        lines.append(f"Menu “{menu.get('label', code)}”: đánh dấu đã xem")
    return lines


def _visible_menus(saved: dict[str, Any], draft: dict[str, Any], q: str, filter_value: str) -> dict[str, list[dict[str, Any]]]:
    """Mã nhóm -> danh sách menu trong bản nháp khớp tìm kiếm/bộ lọc."""
    q_norm = (q or "").strip().lower()
    out: dict[str, list[dict[str, Any]]] = {}
    for group in draft.get("groups", []):
        saved_group = _group_index(saved).get(group["code"], {})
        group_matches_q = bool(q_norm) and q_norm in group["label"].lower()
        shown: list[dict[str, Any]] = []
        for menu in group.get("menus", []):
            saved_menu = _menu_index(saved).get(menu["code"], {})
            if q_norm and not group_matches_q:
                hay = f"{menu['label']} {menu['code']} {menu['path']}".lower()
                if q_norm not in hay:
                    continue
            if filter_value == "hidden" and not menu["is_hidden"]:
                continue
            if filter_value == "new" and not menu["is_new"]:
                continue
            if filter_value == "removed" and not menu["is_removed"]:
                continue
            if filter_value == "changed" and not _menu_changed(saved_menu, menu):
                continue
            shown.append(menu)
        group_visible = bool(shown)
        if filter_value == "changed" and _group_changed(saved_group, group):
            group_visible = True
        if filter_value == "removed" and group.get("is_removed"):
            group_visible = True
        if group_visible:
            out[group["code"]] = shown
    return out


# ---------- Render ----------


def _status_badges(menu: dict[str, Any]) -> Any:
    badges: list[Any] = []
    if menu["is_removed"]:
        badges.append(dmc.Badge("Đã gỡ khỏi code", size="xs", color="gray", variant="light"))
    elif menu["is_hidden"]:
        badges.append(dmc.Badge("Đang ẩn", size="xs", color="red", variant="light"))
    else:
        badges.append(dmc.Badge("Hiển thị", size="xs", color="green", variant="light"))
    if menu["is_new"]:
        badges.append(dmc.Badge("Mới", size="xs", color="green", variant="light"))
    if not menu["is_hideable"]:
        badges.append(dmc.Badge("Bắt buộc", size="xs", color="gray", variant="light"))
    items: list[Any] = [dmc.Group(badges, gap="xs")]
    if menu["is_hidden"] and menu.get("hidden_reason"):
        items.append(dmc.Text(menu["hidden_reason"], size="xs", c="dimmed", mt=4))
    return html.Div(items)


def render_menus_table(saved: dict[str, Any], draft: dict[str, Any], q: str = "", filter_value: str = "all") -> Any:
    """Bảng nhóm + menu theo Screen15. Nhóm và menu đổi so với bản đã
    lưu có vạch tím ở cạnh trái; nút ↑↓ khóa ở đầu/cuối nhóm."""
    groups = _group_index(draft)
    saved_groups = _group_index(saved)
    visible = _visible_menus(saved, draft, q, filter_value)
    all_group_codes = [g["code"] for g in draft.get("groups", [])]

    if not visible:
        return html.Div(
            [
                empty_state(
                    "Không có menu khớp bộ lọc",
                    "Thử từ khóa khác hoặc chọn bộ lọc khác.",
                ),
                dmc.Group(
                    [button_subtle("Xóa bộ lọc", id="menus-clear-filter-btn")],
                    justify="center",
                    mt="md",
                ),
            ]
        )

    rows: list[Any] = []
    for group in draft.get("groups", []):
        gcode = group["code"]
        if gcode not in visible:
            continue
        menus = visible[gcode]
        saved_group = saved_groups.get(gcode, {})
        group_changed = _group_changed(saved_group, group) if saved_group else False
        g_pos = all_group_codes.index(gcode)
        group_row_style = {"boxShadow": "inset 3px 0 0 var(--mantine-color-violet-6)"} if group_changed else None
        rows.append(
            dmc.TableTr(
                dmc.TableTd(
                    dmc.Group(
                        [
                            dmc.Group(
                                [
                                    dmc.ActionIcon(
                                        DashIconify(icon="lucide:chevron-up", width=16),
                                        id={"type": "menus-group-up", "index": gcode},
                                        variant="subtle",
                                        size="sm",
                                        disabled=g_pos == 0,
                                        **{"aria-label": f"Di chuyển nhóm {group['label']} lên"},
                                    ),
                                    dmc.ActionIcon(
                                        DashIconify(icon="lucide:chevron-down", width=16),
                                        id={"type": "menus-group-down", "index": gcode},
                                        variant="subtle",
                                        size="sm",
                                        disabled=g_pos == len(all_group_codes) - 1,
                                        **{"aria-label": f"Di chuyển nhóm {group['label']} xuống"},
                                    ),
                                ],
                                gap=0,
                            ),
                            html.Div(
                                [
                                    dmc.TextInput(
                                        id={"type": "menus-group-label-input", "index": gcode},
                                        value=group["label"],
                                        debounce=500,
                                        disabled=bool(group.get("is_removed")),
                                        style={"width": 220},
                                    ),
                                    dmc.Text(
                                        f"Mặc định: {group['source_label']}",
                                        size="xs",
                                        c="dimmed",
                                        mt=2,
                                    ),
                                ]
                            ),
                            dmc.Text(group["code"], size="xs", c="dimmed", ff="monospace"),
                            dmc.Badge(f"{len(group['menus'])} menu", size="xs", color="gray", variant="light"),
                            button_subtle(
                                "Mặc định",
                                id={"type": "menus-group-reset-btn", "index": gcode},
                                disabled=not group_changed,
                            ),
                        ],
                        gap="md",
                        align="center",
                    ),
                    tableProps={"colSpan": 7},
                ),
                style=group_row_style,
            )
        )
        for pos, menu in enumerate(menus):
            saved_menu = _menu_index(saved).get(menu["code"], {})
            changed = _menu_changed(saved_menu, menu) if saved_menu else False
            row_style = {"boxShadow": "inset 3px 0 0 var(--mantine-color-violet-6)"} if changed else None
            removed = bool(menu["is_removed"])
            if menu["code"] in _ADMIN_ONLY_CODES:
                role_chip = dmc.Badge("Admin", size="xs", color="gray", variant="light")
            elif menu["role_count"]:
                role_chip = dmc.Badge(f"{menu['role_count']} vai trò", size="xs", color="blue", variant="light")
            else:
                role_chip = dmc.Text("—", size="sm", c="dimmed")
            group_options = [{"label": groups[code]["label"], "value": code} for code in all_group_codes]
            source_group_label = groups.get(menu["source_group"], {}).get("label", menu["source_group"])
            actions: list[Any] = []
            if menu["is_hidden"]:
                actions.append(
                    button_subtle(
                        "Bỏ ẩn",
                        id={"type": "menus-unhide-btn", "index": menu["code"]},
                        disabled=removed,
                    )
                )
            else:
                actions.append(
                    button_subtle(
                        "Tạm ẩn",
                        id={"type": "menus-hide-btn", "index": menu["code"]},
                        disabled=removed or not menu["is_hideable"],
                    )
                )
            if menu["is_new"]:
                actions.append(button_subtle("Đã xem", id={"type": "menus-seen-btn", "index": menu["code"]}))
            actions.append(
                button_subtle(
                    "Mặc định",
                    id={"type": "menus-reset-btn", "index": menu["code"]},
                    disabled=not changed,
                )
            )
            rows.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(
                            dmc.Group(
                                [
                                    dmc.ActionIcon(
                                        DashIconify(icon="lucide:chevron-up", width=16),
                                        id={"type": "menus-menu-up", "index": menu["code"]},
                                        variant="subtle",
                                        size="sm",
                                        disabled=pos == 0 or removed,
                                        **{"aria-label": f"Di chuyển {menu['label']} lên"},
                                    ),
                                    dmc.ActionIcon(
                                        DashIconify(icon="lucide:chevron-down", width=16),
                                        id={"type": "menus-menu-down", "index": menu["code"]},
                                        variant="subtle",
                                        size="sm",
                                        disabled=pos == len(menus) - 1 or removed,
                                        **{"aria-label": f"Di chuyển {menu['label']} xuống"},
                                    ),
                                ],
                                gap=0,
                            )
                        ),
                        dmc.TableTd(
                            html.Div(
                                [
                                    dmc.TextInput(
                                        id={"type": "menus-label-input", "index": menu["code"]},
                                        value=menu["label"],
                                        debounce=500,
                                        disabled=removed,
                                        style={"width": 200},
                                    ),
                                    dmc.Text(
                                        f"Mặc định: {menu['source_label']}",
                                        size="xs",
                                        c="dimmed",
                                        mt=2,
                                    ),
                                ]
                            )
                        ),
                        dmc.TableTd(
                            html.Div(
                                [
                                    dmc.Code(menu["code"]),
                                    dmc.Text(menu["path"], size="xs", c="dimmed", mt=2),
                                ]
                            )
                        ),
                        dmc.TableTd(
                            html.Div(
                                [
                                    dmc.Select(
                                        id={"type": "menus-group-select", "index": menu["code"]},
                                        data=group_options,
                                        value=menu["group"],
                                        disabled=removed,
                                        style={"width": 140},
                                    ),
                                    dmc.Text(
                                        f"Mặc định: {source_group_label}",
                                        size="xs",
                                        c="dimmed",
                                        mt=2,
                                    )
                                    if menu["group"] != menu["source_group"]
                                    else None,
                                ]
                            )
                        ),
                        dmc.TableTd(role_chip),
                        dmc.TableTd(_status_badges(menu)),
                        dmc.TableTd(dmc.Group(actions, gap="xs")),
                    ],
                    style=row_style,
                )
            )
    th_style = {
        "position": "sticky",
        "top": 0,
        "zIndex": 1,
        "backgroundColor": "var(--mantine-color-body, #fff)",
        "whiteSpace": "nowrap",
    }
    return dmc.TableScrollContainer(
        minWidth=750,
        children=dmc.Table(
            [
                dmc.TableThead(
                    dmc.TableTr(
                        [
                            dmc.TableTh("Thứ tự", style=th_style),
                            dmc.TableTh("Tên hiển thị", style=th_style),
                            dmc.TableTh("Mã · đường dẫn", style=th_style),
                            dmc.TableTh("Nhóm", style=th_style),
                            dmc.TableTh("Vai trò bật", style=th_style),
                            dmc.TableTh("Trạng thái", style=th_style),
                            dmc.TableTh("Thao tác", style=th_style),
                        ]
                    )
                ),
                dmc.TableTbody(rows),
            ],
            withTableBorder=True,
            withColumnBorders=True,
            highlightOnHover=True,
            verticalSpacing="xs",
        ),
    )


def render_menus_preview(ctx: Ctx, saved: dict[str, Any], draft: dict[str, Any]) -> Any:
    """Khung mô phỏng thanh bên từ bản nháp (menu ẩn/bị gỡ không hiện)."""
    changes = diff_changes(saved, draft)
    res = preview_sidebar(ctx, changes)
    if not res.ok or not isinstance(res.data, list):
        return alert_box(res.message if res else "Không xem trước được thanh bên.", tone="crit")
    nav_groups: list[Any] = []
    for group in res.data:
        items: list[Any] = []
        for item in group.get("items", []):
            items.append(
                dmc.NavLink(
                    label=item["label"],
                    href=item["href"],
                    leftSection=DashIconify(icon=item.get("icon") or "lucide:circle", width=16),
                )
            )
        nav_groups.append(
            html.Div(
                [
                    dmc.Text(group["title"], size="xs", fw=700, c="dimmed", mb=4, mt="sm"),
                    html.Div(items),
                ]
            )
        )
    if not nav_groups:
        return dmc.Text("Không có menu nào hiển thị ở thanh bên.", size="sm", c="dimmed")
    return html.Div(nav_groups)


def render_suspended_preview(draft: dict[str, Any]) -> Any:
    """Khung mô phỏng trang /suspended khi mở một menu đang ẩn."""
    hidden = [m for m in _menu_index(draft).values() if m["is_hidden"]]
    if hidden:
        first = hidden[0]
        detail = (
            f"Ví dụ: menu “{first['label']}” đang ẩn — người dùng mở menu này "
            f"sẽ thấy lý do: “{first.get('hidden_reason') or ''}”."
        )
    else:
        detail = "Khi một menu bị ẩn, người dùng mở menu đó sẽ thấy trang này cùng lý do ẩn."
    return html.Div(
        [
            dmc.Title("Chức năng tạm ngưng", order=4, fw=700),
            dmc.Text(detail, size="sm", c="dimmed", mt="xs"),
        ]
    )


def _alerts(saved: dict[str, Any], draft: dict[str, Any]) -> tuple[Any, Any]:
    new_count = sum(1 for m in _menu_index(draft).values() if m["is_new"])
    removed_count = sum(1 for m in _menu_index(draft).values() if m["is_removed"])
    new_alert = None
    if new_count:
        new_alert = alert_box(
            f"Có {new_count} menu mới từ code chưa được xem.",
            "Bấm “Đã xem” ở từng menu hoặc “Đã xem tất cả” để bỏ nhãn Mới.",
            tone="info",
        )
    removed_alert = None
    if removed_count:
        removed_alert = alert_box(
            f"Có {removed_count} menu đã gỡ khỏi code.",
            "Menu đã gỡ chỉ xem, không sửa được; lọc “Đã gỡ khỏi code” để xem riêng.",
            tone="warn",
        )
    return new_alert, removed_alert


def _dirty_text(saved: dict[str, Any], draft: dict[str, Any]) -> str:
    count = len(diff_changes(saved, draft)) + len(new_flips(saved, draft))
    if not count:
        return "Chưa có thay đổi."
    return f"{count} thay đổi chưa lưu."


def _is_dirty(saved: dict[str, Any], draft: dict[str, Any]) -> bool:
    return bool(diff_changes(saved, draft) or new_flips(saved, draft))


# ---------- Layout ----------


def layout() -> Any:
    """Layout chính màn hình Danh sách menu (Screen15)."""
    ctx = _ctx_or_none()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="menus-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập màn danh sách menu.", tone="crit"),
            ]
        )
    if ctx is None or not is_admin(ctx):
        return html.Div(
            [
                dcc.Location(id="menus-forbidden-redirect", href="/forbidden"),
                alert_box("Bạn không có quyền truy cập màn danh sách menu.", tone="crit"),
            ]
        )

    res = list_menu_tree_admin(ctx)
    if not res.ok or not isinstance(res.data, dict):
        return html.Div(
            id="menus-page-root",
            children=[
                dmc.Title("Danh sách menu", order=2, fw=700),
                html.Div(
                    id="menus-error-box",
                    children=[
                        alert_box(res.message if res else "Không tải được danh sách menu.", tone="crit"),
                        dmc.Group(
                            [button_primary("Thử lại", id="menus-retry-btn", icon="lucide:refresh-cw")],
                            mt="md",
                        ),
                    ],
                    mt="md",
                ),
                dcc.Store(id="menus-saved-store", data=None),
                dcc.Store(id="menus-draft-store", data=None),
                dcc.Store(id="menus-dirty-store", data=False),
                dcc.Store(id="menus-hide-target-store", data=None),
            ],
        )

    tree: dict[str, Any] = res.data
    new_alert, removed_alert = _alerts(tree, tree)
    return html.Div(
        id="menus-page-root",
        style={
            "height": "calc(100vh - 48px)",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
        },
        children=[
            dcc.Store(id="menus-saved-store", data=tree),
            dcc.Store(id="menus-draft-store", data=tree),
            dcc.Store(id="menus-dirty-store", data=False),
            dcc.Store(id="menus-hide-target-store", data=None),
            html.Div(id="menus-beforeunload-sink", style={"display": "none"}),
            # Header
            page_header(
                title="Danh sách menu",
                subtitle="Menu do code khai báo; chỉnh tên hiển thị, nhóm, thứ tự và tạm ẩn menu tại đây.",
                style={"marginBottom": "4px"},
            ),
            dmc.Box(id="menus-new-alert", children=[new_alert] if new_alert else None),
            dmc.Box(
                id="menus-removed-alert",
                children=[removed_alert] if removed_alert else None,
            ),
            html.Div(id="menus-error-box"),
            dmc.Box(id="menus-toast"),
            # Master–Detail 2 cột
            dmc.Box(
                style={
                    "display": "flex",
                    "flexDirection": "row",
                    "flex": 1,
                    "minHeight": 0,
                    "gap": "12px",
                    "overflow": "hidden",
                },
                children=[
                    # Master (Trái): Table Box
                    dmc.Paper(
                        [
                            dmc.Group(
                                [
                                    dmc.TextInput(
                                        id="menus-search-input",
                                        placeholder="Tìm menu theo tên, mã hoặc đường dẫn",
                                        leftSection=DashIconify(icon="lucide:search", width=14),
                                        debounce=300,
                                        size="xs",
                                        style={"flex": 1},
                                    ),
                                    dmc.Select(
                                        id="menus-filter-select",
                                        data=_FILTER_OPTIONS,
                                        value="all",
                                        size="xs",
                                        style={"width": 180},
                                    ),
                                    button_subtle(
                                        "Khôi phục mặc định",
                                        id="menus-reset-all-btn",
                                        icon="lucide:rotate-ccw",
                                        size="xs",
                                    ),
                                    button_subtle(
                                        "Đã xem tất cả",
                                        id="menus-mark-all-seen-btn",
                                        icon="lucide:check-check",
                                        size="xs",
                                    ),
                                ],
                                mb="xs",
                                gap="xs",
                            ),
                            html.Div(
                                id="menus-table-box",
                                children=[render_menus_table(tree, tree)],
                                style={"flex": 1, "minHeight": 0, "overflowY": "auto"},
                            ),
                        ],
                        withBorder=True,
                        radius="sm",
                        p="xs",
                        style={
                            "flex": 1,
                            "minWidth": 0,
                            "minHeight": 0,
                            "height": "100%",
                            "display": "flex",
                            "flexDirection": "column",
                        },
                    ),
                    # Detail (Phải): Preview Box
                    dmc.Paper(
                        [
                            dmc.Paper(
                                [
                                    dmc.Text("Xem trước thanh bên", fw=700, size="sm", mb="xs"),
                                    html.Div(
                                        id="menus-preview-box",
                                        children=[render_menus_preview(ctx, tree, tree)],
                                    ),
                                ],
                                withBorder=True,
                                radius="sm",
                                p="xs",
                                bg="gray.1",
                                mb="xs",
                            ),
                            dmc.Paper(
                                [
                                    dmc.Text(
                                        "Trang khi menu bị ẩn",
                                        fw=700,
                                        size="sm",
                                        mb="xs",
                                    ),
                                    html.Div(
                                        id="menus-suspended-box",
                                        children=[render_suspended_preview(tree)],
                                    ),
                                ],
                                withBorder=True,
                                radius="sm",
                                p="xs",
                                bg="gray.1",
                            ),
                        ],
                        withBorder=True,
                        radius="sm",
                        p="xs",
                        style={
                            "width": "340px",
                            "minWidth": "340px",
                            "maxWidth": "340px",
                            "minHeight": 0,
                            "height": "100%",
                            "overflowY": "auto",
                            "display": "flex",
                            "flexDirection": "column",
                        },
                    ),
                ],
            ),
            # Sticky dirty bar ở chân
            dmc.Paper(
                dmc.Group(
                    [
                        dmc.Text(
                            _dirty_text(tree, tree),
                            id="menus-dirty-text",
                            size="sm",
                            c="dimmed",
                        ),
                        dmc.Group(
                            [
                                button_subtle("Hủy thay đổi", id="menus-discard-btn", disabled=True, size="xs"),
                                button_primary("Lưu", id="menus-save-btn", disabled=True, size="xs"),
                            ],
                            gap="xs",
                        ),
                    ],
                    justify="space-between",
                ),
                withBorder=True,
                radius="sm",
                p="xs",
                mt="xs",
                style={"flexShrink": 0},
            ),
            dmc.Modal(
                id="menus-hide-modal",
                title="Tạm ẩn menu",
                opened=False,
                children=[
                    html.Div(id="menus-hide-modal-body"),
                    dmc.Textarea(
                        id="menus-hide-reason",
                        label="Lý do tạm ẩn",
                        placeholder="VD: Đang bảo trì, mở lại sau khi nâng cấp xong",
                        required=True,
                        inputProps={"maxLength": 300},
                        autosize=True,
                        minRows=2,
                        mt="sm",
                    ),
                    html.Div(id="menus-hide-error"),
                    dmc.Group(
                        [
                            button_subtle("Hủy", id="menus-hide-cancel"),
                            button_primary("Tạm ẩn", id="menus-hide-confirm"),
                        ],
                        justify="flex-end",
                        mt="lg",
                    ),
                ],
            ),
            dmc.Modal(
                id="menus-save-modal",
                title="Lưu thay đổi",
                opened=False,
                children=[
                    html.Div(id="menus-save-modal-body"),
                    html.Div(id="menus-save-error"),
                    dmc.Group(
                        [
                            button_subtle("Hủy", id="menus-save-cancel"),
                            button_primary("Lưu", id="menus-save-confirm"),
                        ],
                        justify="flex-end",
                        mt="lg",
                    ),
                ],
            ),
        ],
    )


# ---------- Callbacks ----------


def _update_draft(draft: dict[str, Any], code: str, **fields: Any) -> dict[str, Any]:
    new_draft = copy.deepcopy(draft)
    menu = _menu_index(new_draft).get(code)
    if menu is None:
        raise dash.exceptions.PreventUpdate
    menu.update(fields)
    return new_draft


@callback(
    Output("menus-table-box", "children"),
    Output("menus-preview-box", "children"),
    Output("menus-suspended-box", "children"),
    Output("menus-new-alert", "children"),
    Output("menus-removed-alert", "children"),
    Output("menus-dirty-text", "children"),
    Output("menus-save-btn", "disabled"),
    Output("menus-discard-btn", "disabled"),
    Output("menus-mark-all-seen-btn", "disabled"),
    Output("menus-dirty-store", "data"),
    Input("menus-draft-store", "data"),
    Input("menus-search-input", "value"),
    Input("menus-filter-select", "value"),
    State("menus-saved-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_render(
    draft: dict[str, Any] | None,
    q: str | None,
    filter_value: str | None,
    saved: dict[str, Any] | None,
) -> Any:
    ctx = _ctx_or_none()
    if ctx is None or not saved or not draft:
        raise dash.exceptions.PreventUpdate
    new_alert, removed_alert = _alerts(saved, draft)
    dirty = _is_dirty(saved, draft)
    has_new = any(m["is_new"] for m in _menu_index(draft).values())
    return (
        render_menus_table(saved, draft, q=q or "", filter_value=filter_value or "all"),
        render_menus_preview(ctx, saved, draft),
        render_suspended_preview(draft),
        [new_alert] if new_alert else None,
        [removed_alert] if removed_alert else None,
        _dirty_text(saved, draft),
        not dirty,
        not dirty,
        not has_new,
        dirty,
    )


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input({"type": "menus-label-input", "index": ALL}, "value"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_label_change(values: list[str | None], draft: dict[str, Any] | None) -> Any:
    if not draft:
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate
    # Vị trí của ô vừa đổi trong danh sách ALL bằng thứ tự render.
    inputs_list = dash.callback_context.inputs_list[0]
    pos = next(
        (i for i, item in enumerate(inputs_list) if item.get("id") == triggered),
        None,
    )
    if pos is None or values[pos] is None:
        raise dash.exceptions.PreventUpdate
    return _update_draft(draft, str(triggered["index"]), label=values[pos])


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input({"type": "menus-group-label-input", "index": ALL}, "value"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_group_label_change(values: list[str | None], draft: dict[str, Any] | None) -> Any:
    if not draft:
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate
    inputs_list = dash.callback_context.inputs_list[0]
    pos = next(
        (i for i, item in enumerate(inputs_list) if item.get("id") == triggered),
        None,
    )
    if pos is None or values[pos] is None:
        raise dash.exceptions.PreventUpdate
    code = str(triggered["index"])
    new_draft = copy.deepcopy(draft)
    for group in new_draft.get("groups", []):
        if group["code"] == code:
            group["label"] = values[pos]
            return new_draft
    raise dash.exceptions.PreventUpdate


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input({"type": "menus-group-select", "index": ALL}, "value"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_group_change(values: list[str | None], draft: dict[str, Any] | None) -> Any:
    if not draft:
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate
    inputs_list = dash.callback_context.inputs_list[0]
    pos = next(
        (i for i, item in enumerate(inputs_list) if item.get("id") == triggered),
        None,
    )
    if pos is None or values[pos] is None:
        raise dash.exceptions.PreventUpdate
    code = str(triggered["index"])
    new_group = str(values[pos])
    new_draft = copy.deepcopy(draft)
    menu = _menu_index(new_draft).get(code)
    if menu is None or menu["group"] == new_group:
        raise dash.exceptions.PreventUpdate
    siblings = [m for m in _menu_index(new_draft).values() if m["group"] == new_group]
    menu["group"] = new_group
    menu["order"] = (max((m["order"] for m in siblings), default=0) + 10) if siblings else 10
    return new_draft


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input({"type": "menus-menu-up", "index": ALL}, "n_clicks"),
    Input({"type": "menus-menu-down", "index": ALL}, "n_clicks"),
    Input({"type": "menus-group-up", "index": ALL}, "n_clicks"),
    Input({"type": "menus-group-down", "index": ALL}, "n_clicks"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_move(
    _up: list[int | None],
    _down: list[int | None],
    _gup: list[int | None],
    _gdown: list[int | None],
    draft: dict[str, Any] | None,
) -> Any:
    if not draft:
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict) or not any([*_up, *_down, *_gup, *_gdown]):
        raise dash.exceptions.PreventUpdate
    kind = str(triggered["type"])
    code = str(triggered["index"])
    new_draft = copy.deepcopy(draft)
    if kind in ("menus-menu-up", "menus-menu-down"):
        menu = _menu_index(new_draft).get(code)
        if menu is None:
            raise dash.exceptions.PreventUpdate
        siblings = sorted(
            (m for m in _menu_index(new_draft).values() if m["group"] == menu["group"]),
            key=lambda m: m["order"],
        )
        pos = next((i for i, m in enumerate(siblings) if m["code"] == code), None)
        if pos is None:
            raise dash.exceptions.PreventUpdate
        if kind == "menus-menu-up":
            if pos == 0:
                raise dash.exceptions.PreventUpdate
            other = siblings[pos - 1]
        else:
            if pos == len(siblings) - 1:
                raise dash.exceptions.PreventUpdate
            other = siblings[pos + 1]
        menu["order"], other["order"] = other["order"], menu["order"]
        return new_draft
    groups = sorted(new_draft.get("groups", []), key=lambda g: g["order"])
    pos = next((i for i, g in enumerate(groups) if g["code"] == code), None)
    if pos is None:
        raise dash.exceptions.PreventUpdate
    if kind == "menus-group-up":
        if pos == 0:
            raise dash.exceptions.PreventUpdate
        other = groups[pos - 1]
    else:
        if pos == len(groups) - 1:
            raise dash.exceptions.PreventUpdate
        other = groups[pos + 1]
    mine = next(g for g in new_draft["groups"] if g["code"] == code)
    mine["order"], other["order"] = other["order"], mine["order"]
    return new_draft


@callback(
    Output("menus-hide-modal", "opened"),
    Output("menus-hide-target-store", "data"),
    Output("menus-hide-modal-body", "children"),
    Output("menus-hide-reason", "value"),
    Output("menus-hide-error", "children"),
    Input({"type": "menus-hide-btn", "index": ALL}, "n_clicks"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_hide_open(
    n_clicks_list: list[int | None],
    draft: dict[str, Any] | None,
) -> Any:
    if not draft or not any(n_clicks_list):
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate
    code = str(triggered["index"])
    menu = _menu_index(draft).get(code)
    if menu is None:
        raise dash.exceptions.PreventUpdate
    body = dmc.Text(
        f"Tạm ẩn menu “{menu['label']}”. {menu['role_count']} vai trò đang dùng menu này "
        "sẽ không thấy menu nữa cho tới khi bỏ ẩn.",
        size="sm",
        c="dimmed",
    )
    return True, code, body, None, None


@callback(
    Output("menus-hide-modal", "opened", allow_duplicate=True),
    Input("menus-hide-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def handle_menus_hide_cancel(_n: int | None) -> Any:
    if not _n:
        raise dash.exceptions.PreventUpdate
    return False


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Output("menus-hide-modal", "opened", allow_duplicate=True),
    Output("menus-hide-error", "children", allow_duplicate=True),
    Input("menus-hide-confirm", "n_clicks"),
    State("menus-hide-reason", "value"),
    State("menus-hide-target-store", "data"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_hide_confirm(
    n_clicks: int | None,
    reason: str | None,
    code: str | None,
    draft: dict[str, Any] | None,
) -> Any:
    if not n_clicks or not code or not draft:
        raise dash.exceptions.PreventUpdate
    clean = (reason or "").strip()
    if not clean:
        return dash.no_update, True, alert_box("Nhập lý do tạm ẩn.", tone="crit")
    if len(clean) > 300:
        return dash.no_update, True, alert_box("Lý do tối đa 300 ký tự.", tone="crit")
    return _update_draft(draft, code, is_hidden=True, hidden_reason=clean), False, None


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input({"type": "menus-unhide-btn", "index": ALL}, "n_clicks"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_unhide(n_clicks_list: list[int | None], draft: dict[str, Any] | None) -> Any:
    if not draft or not any(n_clicks_list):
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate
    return _update_draft(draft, str(triggered["index"]), is_hidden=False, hidden_reason=None)


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input({"type": "menus-seen-btn", "index": ALL}, "n_clicks"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_mark_seen(n_clicks_list: list[int | None], draft: dict[str, Any] | None) -> Any:
    if not draft or not any(n_clicks_list):
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate
    return _update_draft(draft, str(triggered["index"]), is_new=False)


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input("menus-mark-all-seen-btn", "n_clicks"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_mark_all_seen(n_clicks: int | None, draft: dict[str, Any] | None) -> Any:
    if not n_clicks or not draft:
        raise dash.exceptions.PreventUpdate
    new_draft = copy.deepcopy(draft)
    for menu in _menu_index(new_draft).values():
        menu["is_new"] = False
    return new_draft


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input({"type": "menus-reset-btn", "index": ALL}, "n_clicks"),
    Input({"type": "menus-group-reset-btn", "index": ALL}, "n_clicks"),
    State("menus-draft-store", "data"),
    State("menus-saved-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_reset_one(
    menu_clicks: list[int | None],
    group_clicks: list[int | None],
    draft: dict[str, Any] | None,
    saved: dict[str, Any] | None,
) -> Any:
    if not draft or not saved or not any([*menu_clicks, *group_clicks]):
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate
    code = str(triggered["index"])
    new_draft = copy.deepcopy(draft)
    if triggered["type"] == "menus-group-reset-btn":
        sg = _group_index(saved).get(code)
        dg = _group_index(new_draft).get(code)
        if sg is None or dg is None:
            raise dash.exceptions.PreventUpdate
        dg["label"] = sg["source_label"]
        dg["order"] = sg["source_order"]
        return new_draft
    sm = _menu_index(saved).get(code)
    dm = _menu_index(new_draft).get(code)
    if sm is None or dm is None:
        raise dash.exceptions.PreventUpdate
    dm["label"] = sm["source_label"]
    dm["group"] = sm["source_group"]
    dm["order"] = sm["source_order"]
    dm["is_hidden"] = sm["is_hidden"]
    dm["hidden_reason"] = sm["hidden_reason"]
    return new_draft


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input("menus-reset-all-btn", "n_clicks"),
    State("menus-draft-store", "data"),
    State("menus-saved-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_reset_all(
    n_clicks: int | None,
    draft: dict[str, Any] | None,
    saved: dict[str, Any] | None,
) -> Any:
    if not n_clicks or not draft or not saved:
        raise dash.exceptions.PreventUpdate
    new_draft = copy.deepcopy(draft)
    saved_groups = _group_index(saved)
    for group in new_draft.get("groups", []):
        sg = saved_groups.get(group["code"])
        if sg is not None:
            group["label"] = sg["source_label"]
            group["order"] = sg["source_order"]
    saved_menus = _menu_index(saved)
    for menu in _menu_index(new_draft).values():
        sm = saved_menus.get(menu["code"])
        if sm is not None:
            menu["label"] = sm["source_label"]
            menu["group"] = sm["source_group"]
            menu["order"] = sm["source_order"]
    return new_draft


@callback(
    Output("menus-draft-store", "data", allow_duplicate=True),
    Input("menus-discard-btn", "n_clicks"),
    State("menus-saved-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_discard(n_clicks: int | None, saved: dict[str, Any] | None) -> Any:
    if not n_clicks or not saved:
        raise dash.exceptions.PreventUpdate
    return copy.deepcopy(saved)


@callback(
    Output("menus-save-modal", "opened"),
    Output("menus-save-modal-body", "children"),
    Output("menus-save-error", "children"),
    Input("menus-save-btn", "n_clicks"),
    State("menus-saved-store", "data"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_save_open(
    n_clicks: int | None,
    saved: dict[str, Any] | None,
    draft: dict[str, Any] | None,
) -> Any:
    if not n_clicks or not saved or not draft:
        raise dash.exceptions.PreventUpdate
    if not _is_dirty(saved, draft):
        raise dash.exceptions.PreventUpdate
    lines = describe_changes(saved, draft)
    body = html.Ul([html.Li(line) for line in lines])
    return True, body, None


@callback(
    Output("menus-save-modal", "opened", allow_duplicate=True),
    Input("menus-save-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def handle_menus_save_cancel(_n: int | None) -> Any:
    if not _n:
        raise dash.exceptions.PreventUpdate
    return False


@callback(
    Output("menus-saved-store", "data", allow_duplicate=True),
    Output("menus-draft-store", "data", allow_duplicate=True),
    Output("menus-save-modal", "opened", allow_duplicate=True),
    Output("menus-save-error", "children", allow_duplicate=True),
    Output("menus-toast", "children"),
    Input("menus-save-confirm", "n_clicks"),
    State("menus-saved-store", "data"),
    State("menus-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_menus_save_confirm(
    n_clicks: int | None,
    saved: dict[str, Any] | None,
    draft: dict[str, Any] | None,
) -> Any:
    ctx = _ctx_or_none()
    if not n_clicks or ctx is None or not saved or not draft:
        raise dash.exceptions.PreventUpdate
    changes = diff_changes(saved, draft)
    flips = new_flips(saved, draft)
    if not changes and not flips:
        raise dash.exceptions.PreventUpdate
    if changes:
        res = save_menu_changes(ctx, changes)
        if not res.ok:
            return (
                dash.no_update,
                dash.no_update,
                True,
                alert_box(res.message, tone="crit"),
                dash.no_update,
            )
    for code in flips:
        mark_seen(ctx, code)
    fresh = list_menu_tree_admin(ctx)
    if not fresh.ok or not isinstance(fresh.data, dict):
        return (
            dash.no_update,
            dash.no_update,
            True,
            alert_box("Đã lưu nhưng không tải lại được danh sách.", tone="crit"),
            dash.no_update,
        )
    count = len(changes) + len(flips)
    return (
        fresh.data,
        copy.deepcopy(fresh.data),
        False,
        None,
        alert_box(f"Đã lưu {count} thay đổi.", tone="ok"),
    )


@callback(
    Output("menus-saved-store", "data", allow_duplicate=True),
    Output("menus-draft-store", "data", allow_duplicate=True),
    Output("menus-error-box", "children"),
    Input("menus-retry-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_menus_retry(n_clicks: int | None) -> Any:
    ctx = _ctx_or_none()
    if not n_clicks or ctx is None:
        raise dash.exceptions.PreventUpdate
    res = list_menu_tree_admin(ctx)
    if not res.ok or not isinstance(res.data, dict):
        return (
            dash.no_update,
            dash.no_update,
            alert_box(res.message if res else "Không tải được danh sách menu.", tone="crit"),
        )
    return res.data, copy.deepcopy(res.data), None


@callback(
    Output("menus-search-input", "value"),
    Output("menus-filter-select", "value"),
    Input("menus-clear-filter-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_menus_clear_filter(n_clicks: int | None) -> Any:
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return "", "all"


# Cảnh báo rời trang khi còn thay đổi chưa lưu (Q6). Không có tiền lệ
# clientside_callback trong app/ nên đây là lần đầu dùng; nếu không ổn
# định sẽ bỏ và ghi vào decisions.md.
clientside_callback(
    """
    function(dirty) {
        if (dirty) {
            window.onbeforeunload = function(e) {
                e.preventDefault();
                e.returnValue = '';
                return '';
            };
        } else {
            window.onbeforeunload = null;
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("menus-beforeunload-sink", "children"),
    Input("menus-dirty-store", "data"),
    prevent_initial_call=True,
)
