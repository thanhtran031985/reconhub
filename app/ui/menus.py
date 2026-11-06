"""Khai báo danh sách menu trong code (task 19, spec 11 mục 2.1).

`code` là khóa bất biến; mỗi page Dash và mỗi service khai báo
`menu_code` mà nó thuộc về. Danh sách này tự đồng bộ vào DB khi khởi
động qua `app.services.menu_sync`. Không import DMC ở đây để migration
và test có thể dùng chung mà không kéo giao diện.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroupDef:
    code: str
    label: str
    order: int


@dataclass(frozen=True)
class MenuDef:
    code: str
    label: str
    group: str
    path: str
    order: int
    icon: str
    # "Y" = Admin được tạm ẩn, "N" = menu bắt buộc của quản trị
    hideable: str = "Y"


GROUPS: list[GroupDef] = [
    GroupDef("DOI_SOAT", "Đối soát", 10),
    GroupDef("CAU_HINH", "Cấu hình", 20),
    GroupDef("QUAN_TRI", "Quản trị", 30),
]

# Đường dẫn history giữ "/history" theo Q3 (code hiện tại), khác bảng
# seed 11a mục 7 ghi "/runs".
MENUS: list[MenuDef] = [
    MenuDef("dashboard", "Dashboard", "DOI_SOAT", "/", 10, "lucide:layout-dashboard"),
    MenuDef("run", "Chạy đối soát", "DOI_SOAT", "/runs/new", 20, "lucide:play"),
    MenuDef("result", "Kết quả run", "DOI_SOAT", "/runs/<id>", 30, "lucide:file-text"),
    MenuDef("batch_run", "Chạy bộ đối soát", "DOI_SOAT", "/batch-runs", 40, "lucide:layers"),
    MenuDef("history", "Lịch sử", "DOI_SOAT", "/history", 50, "lucide:history"),
    MenuDef("issue", "Xử lý chênh lệch", "DOI_SOAT", "/issues", 60, "lucide:alert-circle"),
    MenuDef("template", "Templates", "CAU_HINH", "/templates", 10, "lucide:file-spreadsheet"),
    MenuDef("batch_def", "Bộ đối soát", "CAU_HINH", "/batches", 20, "lucide:layers"),
    MenuDef("data_source", "Data Sources", "CAU_HINH", "/data-sources", 30, "lucide:database"),
    MenuDef("lookup", "Danh mục hệ thống", "CAU_HINH", "/lookups", 40, "lucide:list"),
    MenuDef("user", "Người dùng", "QUAN_TRI", "/users", 10, "lucide:users", "N"),
    MenuDef("role", "Vai trò và phân quyền", "QUAN_TRI", "/roles", 20, "lucide:shield", "N"),
    MenuDef("menu_admin", "Danh sách menu", "QUAN_TRI", "/menus", 30, "lucide:list", "N"),
    MenuDef("report_center", "Trung tâm báo cáo", "DOI_SOAT", "/reports", 70, "lucide:bar-chart-3"),
    MenuDef("report_history", "Lịch sử báo cáo", "DOI_SOAT", "/report-runs", 80, "lucide:clipboard-list"),
    MenuDef("report_admin", "Quản trị báo cáo", "QUAN_TRI", "/report-admin", 40, "lucide:settings", "N"),
]

MENU_BY_CODE: dict[str, MenuDef] = {m.code: m for m in MENUS}
GROUP_BY_CODE: dict[str, GroupDef] = {g.code: g for g in GROUPS}

# Vai trò seed -> menu, theo spec 11a mục 7. ADMIN không có dòng
# (quyền tính theo IS_SYSTEM). Dùng cho migration seed và đường lui
# của effective_menus khi ctx không phải user trong DB (CLI, worker).
# Task 21 (Q1): report_center + report_history cho cả 3 vai trò còn lại,
# report_admin chỉ ADMIN.
ROLE_MENUS_SEED: dict[str, list[str]] = {
    "TEMPLATE_OWNER": [
        "dashboard",
        "run",
        "result",
        "batch_run",
        "history",
        "issue",
        "template",
        "batch_def",
        "report_center",
        "report_history",
    ],
    "OPERATOR": [
        "dashboard",
        "run",
        "result",
        "batch_run",
        "history",
        "issue",
        "report_center",
        "report_history",
    ],
    "VIEWER": [
        "dashboard",
        "result",
        "history",
        "template",
        "batch_def",
        "report_center",
        "report_history",
    ],
}


def menu_label(code: str) -> str:
    """Tên hiển thị mặc định (từ code) của một menu."""
    menu = MENU_BY_CODE.get(code)
    return menu.label if menu else code
