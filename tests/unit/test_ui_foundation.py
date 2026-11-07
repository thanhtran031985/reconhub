from __future__ import annotations

import dash_ag_grid as dag
import dash_mantine_components as dmc

from app.core.context import Ctx, Role
from app.ui.components import (
    DIFF_CELL_CLASS_RULES,
    GRID_DEFAULTS,
    HEADER_HEIGHT,
    ROW_HEIGHT,
    alert_box,
    button_danger,
    button_primary,
    button_subtle,
    code_block,
    command_bar,
    data_grid,
    drawer_right,
    empty_state,
    error_state,
    file_drop,
    filter_bar,
    form_field,
    kpi_card,
    master_detail_layout,
    modal_confirm,
    page_header,
    skeleton_grid,
    skeleton_panel,
    status_chip,
    wizard_shell,
)
from app.ui.layout.shell import create_header, create_navbar, sync_sidebar_ui


def test_backward_compatibility_exports() -> None:
    """Đảm bảo toàn bộ component cũ tiếp tục export không bị vỡ contract."""
    assert callable(status_chip)
    assert callable(form_field)
    assert callable(kpi_card)
    assert callable(alert_box)
    assert callable(empty_state)
    assert callable(button_primary)
    assert callable(button_danger)
    assert callable(button_subtle)
    assert callable(modal_confirm)
    assert callable(drawer_right)
    assert callable(file_drop)
    assert callable(code_block)


def test_grid_defaults_constants() -> None:
    """Kiểm tra các hằng số Fluent Compact cho AgGrid."""
    assert ROW_HEIGHT == 32
    assert HEADER_HEIGHT == 34
    assert GRID_DEFAULTS["rowHeight"] == 32
    assert GRID_DEFAULTS["headerHeight"] == 34
    assert GRID_DEFAULTS["animateRows"] is False
    assert GRID_DEFAULTS["suppressCellFocus"] is True
    assert "rh-diff" in DIFF_CELL_CLASS_RULES
    assert "rh-diff-num" in DIFF_CELL_CLASS_RULES


def test_data_grid_component() -> None:
    """Kiểm tra wrapper data_grid đóng gói đúng defaults và styles."""
    col_defs = [{"field": "id", "headerName": "ID"}, {"field": "name", "headerName": "Tên"}]
    row_data = [{"id": 1, "name": "Item 1"}]

    box = data_grid(
        id="test-grid",
        columnDefs=col_defs,
        rowData=row_data,
        rowModelType="clientSide",
    )
    assert isinstance(box, dmc.Box)

    grid = box.children
    assert isinstance(grid, dag.AgGrid)
    assert grid.id == "test-grid"
    assert grid.columnDefs == col_defs
    assert grid.rowData == row_data
    assert grid.dashGridOptions["rowHeight"] == 32
    assert grid.dashGridOptions["headerHeight"] == 34
    assert grid.dashGridOptions["rowModelType"] == "clientSide"
    assert grid.className == "ag-theme-quartz-auto-dark"

    # Infinite model test
    box_inf = data_grid(
        id="test-grid-inf",
        columnDefs=col_defs,
        rowModelType="infinite",
    )
    grid_inf = box_inf.children
    assert isinstance(grid_inf, dag.AgGrid)
    assert grid_inf.dashGridOptions["rowModelType"] == "infinite"


def test_page_header_component() -> None:
    """Kiểm tra page_header chuẩn 1 dòng compact."""
    btn = button_primary("Tạo mới", id="btn-create")
    header = page_header(
        title="Danh sách Template",
        subtitle="Quản lý cấu hình đối soát",
        actions=[btn],
        breadcrumbs=[{"label": "Trang chủ", "href": "/"}, {"label": "Templates"}],
        id="test-header",
    )
    assert isinstance(header, dmc.Box)
    assert header.id == "test-header"
    # Header chứa Breadcrumbs và Group tiêu đề + action
    assert len(header.children) == 2


def test_command_bar_component() -> None:
    """Kiểm tra thanh CommandBar tìm kiếm và hành động."""
    btn = button_subtle("Làm mới", id="btn-refresh")
    cmd = command_bar(
        search_id="tbl-search",
        search_placeholder="Tìm theo mã...",
        filters=[dmc.Badge("Đang chạy")],
        actions=[btn],
        id="test-cmd",
    )
    assert isinstance(cmd, dmc.Paper)
    assert cmd.id == "test-cmd"


def test_filter_bar_component() -> None:
    """Kiểm tra thanh FilterBar lọc dữ liệu."""
    fb = filter_bar(
        children=[dmc.TextInput(id="f-name", placeholder="Tên")],
        actions=[button_primary("Áp dụng", id="btn-apply")],
        id="test-filter-bar",
    )
    assert isinstance(fb, dmc.Paper)
    assert fb.id == "test-filter-bar"


def test_master_detail_layout() -> None:
    """Kiểm tra MasterDetailLayout chia 2 cột responsive."""
    master = dmc.Box("Master content", id="master-box")
    detail = dmc.Box("Detail content", id="detail-box")

    # Visible detail
    layout = master_detail_layout(
        master_content=master,
        detail_content=detail,
        detail_width=380,
        detail_visible=True,
        id="test-md",
    )
    assert isinstance(layout, dmc.Box)
    assert len(layout.children) == 2

    # Hidden detail
    layout_hidden = master_detail_layout(
        master_content=master,
        detail_content=detail,
        detail_visible=False,
    )
    assert len(layout_hidden.children) == 1


def test_wizard_shell_component() -> None:
    """Kiểm tra WizardShell layout 3 phần (stepper, body, footer)."""
    steps = [
        {"label": "Thông tin chung"},
        {"label": "Nguồn dữ liệu"},
        {"label": "Mapping cột"},
    ]
    wiz = wizard_shell(
        steps=steps,
        current_step=1,
        content=dmc.Box("Bước 2 form"),
        footer_actions=[button_primary("Tiếp tục", id="btn-next")],
        id="test-wiz",
    )
    assert isinstance(wiz, dmc.Box)
    assert wiz.id == "test-wiz"
    assert len(wiz.children) == 2  # Stepper bar + Body & Footer container


def test_skeleton_helpers() -> None:
    """Kiểm tra SkeletonGrid và SkeletonPanel."""
    grid_sk = skeleton_grid(rows=6, cols=3, id="sk-grid")
    assert isinstance(grid_sk, dmc.Box)
    assert grid_sk.id == "sk-grid"
    assert len(grid_sk.children) == 7  # 1 header + 6 rows

    panel_sk = skeleton_panel(lines=4, id="sk-panel")
    assert isinstance(panel_sk, dmc.Box)
    assert panel_sk.id == "sk-panel"


def test_error_state_component() -> None:
    """Kiểm tra ErrorState 4-state và banner_only."""
    # Full error paper
    err_full = error_state(
        title="Lỗi tải dữ liệu",
        message="Không thể kết nối máy chủ",
        retry_id="btn-retry",
        id="err-full",
    )
    assert isinstance(err_full, dmc.Paper)
    assert err_full.id == "err-full"

    # Banner only alert
    err_banner = error_state(
        title="Lỗi nhẹ",
        message="Vui lòng thử lại",
        retry_id="btn-retry-banner",
        banner_only=True,
        id="err-banner",
    )
    assert isinstance(err_banner, dmc.Alert)
    assert err_banner.id == "err-banner"


def test_app_shell_fluent_refactoring() -> None:
    """Kiểm tra refactor shell: navbar 200px / 48px, header 44px."""
    ctx = Ctx(
        user_id=1,
        username="admin",
        roles=[Role.ADMIN.value],
        full_name="Quản trị viên",
    )

    # 1. Header renders at 44px style
    header = create_header(ctx, "dev", "/templates", is_mini=False)
    assert isinstance(header, dmc.Group)

    # 2. Navbar full (200px)
    nav_full = create_navbar(ctx, "/templates", is_mini=False)
    assert isinstance(nav_full, dmc.Stack)

    # 3. Navbar mini (48px rail)
    nav_mini = create_navbar(ctx, "/templates", is_mini=True)
    assert isinstance(nav_mini, dmc.Stack)

    # 4. sync_sidebar_ui toggle widths
    navbar_cfg_mini, _, toggle_icon_mini, toggle_lbl_mini = sync_sidebar_ui(True, "/templates")
    assert navbar_cfg_mini["width"] == 48
    assert "Mở rộng" in toggle_lbl_mini

    navbar_cfg_full, _, toggle_icon_full, toggle_lbl_full = sync_sidebar_ui(False, "/templates")
    assert navbar_cfg_full["width"] == 200
    assert "Thu nhỏ" in toggle_lbl_full
