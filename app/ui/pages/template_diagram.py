from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import dcc, html

from app.core.session import get_current_ctx
from app.schemas.template_config import TemplateConfig
from app.services.diagram import generate_screen04_diagrams
from app.services.template import get_template
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.code_block import code_block
from app.ui.components.empty_state import empty_state

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path_template="/templates/<template_id>/diagram",
        title="Sơ đồ diễn giải — ReconHub",
    )
except Exception:
    pass


def render_diagram_card(
    title: str,
    subtitle: str,
    diagram_code: str,
    card_id: str,
) -> dmc.Card:
    """Dựng một khối card sơ đồ Mermaid theo thiết kế Screen04."""
    return dmc.Card(
        withBorder=True,
        radius="md",
        p="lg",
        children=[
            dmc.Group(
                justify="space-between",
                align="center",
                mb="xs",
                children=[
                    dmc.Stack(
                        [
                            dmc.Title(title, order=3, size="h4"),
                            dmc.Text(subtitle, size="sm", c="dimmed"),
                        ],
                        gap=2,
                    ),
                    dmc.Group(
                        [
                            dcc.Clipboard(
                                content=diagram_code,
                                title="Sao chép mã Mermaid",
                                style={
                                    "display": "inline-flex",
                                    "alignItems": "center",
                                    "padding": "6px 10px",
                                    "fontSize": "13px",
                                    "borderRadius": "var(--radius-sm, 6px)",
                                    "border": "1px solid var(--border-subtle, #e2e8f0)",
                                    "backgroundColor": "#ffffff",
                                    "cursor": "pointer",
                                },
                            ),
                        ],
                        gap="xs",
                    ),
                ],
            ),
            # Vùng hiển thị sơ đồ Mermaid
            html.Div(
                html.Pre(
                    diagram_code,
                    className="mermaid",
                    id=f"{card_id}-pre",
                    style={
                        "textAlign": "center",
                        "margin": "0 auto",
                        "background": "transparent",
                        "border": "none",
                        "padding": "16px 0",
                    },
                ),
                style={
                    "overflowX": "auto",
                    "backgroundColor": "#f8fafc",
                    "borderRadius": "8px",
                    "padding": "16px",
                    "marginBottom": "12px",
                    "textAlign": "center",
                },
            ),
            # Chi tiết mã nguồn Mermaid (collapsible)
            dmc.Accordion(
                variant="subtle",
                children=[
                    dmc.AccordionItem(
                        value="code",
                        children=[
                            dmc.AccordionControl(
                                dmc.Text("Xem mã nguồn Mermaid", size="xs", c="dimmed"),
                            ),
                            dmc.AccordionPanel(
                                code_block(diagram_code, language="mermaid"),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def layout(template_id: str | None = None, **kwargs: Any) -> Any:
    """Giao diện chính màn hình Sơ đồ diễn giải template (Screen04)."""
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập để xem sơ đồ template.", tone="crit")

    if not template_id:
        return empty_state(
            title="Không tìm thấy template",
            description="Vui lòng chọn template từ danh sách.",
            action=dmc.Anchor(
                button_primary("Danh sách template", icon="lucide:arrow-left"),
                href="/templates",
                underline=False,
            ),
        )

    # 1. Truy vấn cấu hình template
    res = get_template(ctx, template_id=template_id)
    if not res.ok or not res.data:
        return alert_box(
            f"Không thể tải thông tin template '{template_id}'. Lỗi: {res.message}",
            tone="crit",
            action=dmc.Anchor(
                button_subtle("Về danh sách", icon="lucide:arrow-left"),
                href="/templates",
                underline=False,
            ),
        )

    tmpl = res.data
    t_code = tmpl.get("code") or template_id
    t_name = tmpl.get("name") or "Template"
    t_version = tmpl.get("current_version") or 1
    config_dict = tmpl.get("config") or {}

    try:
        cfg = TemplateConfig.model_validate(config_dict)
    except Exception as exc:
        return alert_box(
            f"Cấu hình template không đúng định dạng: {exc!s}",
            tone="crit",
            action=dmc.Anchor(
                button_primary("Sửa cấu hình", icon="lucide:edit-3"),
                href=f"/templates/{template_id}/edit",
                underline=False,
            ),
        )

    # 2. Sinh các sơ đồ Mermaid
    try:
        diagrams = generate_screen04_diagrams(cfg)
    except Exception as exc:
        return alert_box(
            f"Lỗi khi sinh sơ đồ Mermaid: {exc!s}",
            tone="crit",
        )

    # 3. Dựng Breadcrumb và Header
    breadcrumbs = dmc.Breadcrumbs(
        [
            dmc.Anchor("Trang chủ", href="/", size="sm", underline=False),
            dmc.Anchor("Cấu hình", href="#", size="sm", underline=False),
            dmc.Anchor("Templates", href="/templates", size="sm", underline=False),
            dmc.Text(t_code, size="sm", fw=700),
            dmc.Text("Sơ đồ diễn giải", size="sm", c="dimmed"),
        ],
        separator=" / ",
        mb="md",
    )

    header = dmc.Group(
        justify="space-between",
        align="flex-start",
        mb="lg",
        children=[
            dmc.Stack(
                [
                    dmc.Title(f"Sơ đồ diễn giải template: {t_code}", order=1, size="h2"),
                    dmc.Text(
                        f"Sơ đồ trực quan sinh tự động từ cấu hình phiên bản v{t_version} ({t_name}).",
                        size="sm",
                        c="dimmed",
                    ),
                ],
                gap=4,
            ),
            dmc.Group(
                [
                    dmc.Anchor(
                        button_subtle("Danh sách template", icon="lucide:arrow-left"),
                        href="/templates",
                        underline=False,
                    ),
                    dmc.Anchor(
                        button_primary("Sửa cấu hình template", icon="lucide:settings"),
                        href=f"/templates/{template_id}/edit",
                        underline=False,
                    ),
                ],
                gap="sm",
            ),
        ],
    )

    # Tabs điều hướng nhanh (Cấu hình vs Sơ đồ diễn giải)
    nav_tabs = dmc.Group(
        [
            dmc.Anchor(
                button_subtle("Cấu hình template", icon="lucide:sliders"),
                href=f"/templates/{template_id}/edit",
                underline=False,
            ),
            button_primary("Sơ đồ diễn giải", icon="lucide:workflow"),
        ],
        gap="xs",
        mb="lg",
    )

    # 4. Danh sách các Card sơ đồ theo Screen04
    cards: list[Any] = [
        render_diagram_card(
            title="① Quy trình đăng ký template",
            subtitle="Dry-run đạt mới kích hoạt được version mới.",
            diagram_code=diagrams["workflow"],
            card_id="diag-workflow",
        ),
        render_diagram_card(
            title="② Ba lớp mapping (Excel → Logic → DB)",
            subtitle="Tập tin Excel và Oracle Database gặp nhau ở các trường logic chuẩn hóa.",
            diagram_code=diagrams["three_layer"],
            card_id="diag-three-layer",
        ),
        render_diagram_card(
            title="③ Tham số thời gian & Bộ lọc SQL",
            subtitle="Một khoảng ngày giờ do người dùng nhập, áp dụng đồng thời cho cả DB và Excel.",
            diagram_code=diagrams["time_filter"],
            card_id="diag-time-filter",
        ),
        render_diagram_card(
            title="④ Profile: gộp → ghép → so",
            subtitle="Cả hai phía gộp nhóm theo cùng Group by và so sai số chênh lệch theo Measures.",
            diagram_code=diagrams["profile_match"],
            card_id="diag-profile-match",
        ),
        render_diagram_card(
            title="⑤ Trình tự thực thi khi chạy đối soát",
            subtitle="Từ lúc upload file đến khi kiểm tra xong và xử lý chênh lệch.",
            diagram_code=diagrams["sequence"],
            card_id="diag-sequence",
        ),
        render_diagram_card(
            title="⑥ Luồng xử lý dữ liệu tổng quan (Pipeline)",
            subtitle="Toàn cảnh luồng dữ liệu thô, chuẩn hóa, gộp nhóm và phân loại kết quả.",
            diagram_code=diagrams["pipeline"],
            card_id="diag-pipeline",
        ),
    ]

    # Nếu có Control Total thì hiển thị thêm khối Control Total
    if cfg.control_total:
        cards.append(
            render_diagram_card(
                title="⑦ Kiểm tra tổng kiểm soát (Control Total)",
                subtitle="Đối chiếu dòng tổng từ file Excel với tổng cộng dồn dữ liệu chi tiết.",
                diagram_code=diagrams["control_total"],
                card_id="diag-control-total",
            )
        )

    return dmc.Container(
        size="xl",
        py="lg",
        children=[
            breadcrumbs,
            header,
            nav_tabs,
            dmc.Stack(cards, gap="xl"),
        ],
    )
