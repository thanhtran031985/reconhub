from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import dash
import dash_mantine_components as dmc

from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.code_block import code_block
from app.ui.components.empty_state import empty_state
from app.ui.components.field import form_field
from app.ui.components.file_drop import file_drop
from app.ui.components.kpi_card import kpi_card
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.status_chip import status_chip
from app.ui.formatters import format_bytes, format_currency, format_datetime, format_number

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/dev/ui",
        title="Thư viện Component — ReconHub",
    )
except Exception:
    pass


def layout() -> Any:
    return dmc.Container(
        [
            dmc.Stack(
                [
                    dmc.Title("Thư viện thành phần giao diện (UI Gallery)", order=2),
                    dmc.Text("Trưng bày và đối chiếu các component Dash Mantine với designs/components", c="dimmed"),
                    # 1. StatusChip
                    dmc.Paper(
                        [
                            dmc.Title("1. StatusChip (luôn có icon + chữ)", order=4, mb="md"),
                            dmc.Text("Kết quả đối soát:", size="sm", fw=600, mb="xs"),
                            dmc.Group(
                                [
                                    status_chip("MATCHED"),
                                    status_chip("MISMATCH"),
                                    status_chip("MISSING_IN_DB"),
                                    status_chip("MISSING_IN_EXCEL"),
                                    status_chip("INCONSISTENT"),
                                    status_chip("DUPLICATE"),
                                    status_chip("INVALID"),
                                ],
                                gap="xs",
                                mb="md",
                            ),
                            dmc.Text("Người dùng:", size="sm", fw=600, mb="xs"),
                            dmc.Group(
                                [
                                    status_chip("ACTIVE"),
                                    status_chip("LOCKED", label="Tạm khóa đến 15:30"),
                                    status_chip("DISABLED"),
                                    status_chip("MUST_CHANGE_PW"),
                                ],
                                gap="xs",
                                mb="md",
                            ),
                            dmc.Text("Môi trường & Vai trò & Dữ liệu tạm:", size="sm", fw=600, mb="xs"),
                            dmc.Group(
                                [
                                    status_chip("DEV"),
                                    status_chip("UAT"),
                                    status_chip("PROD"),
                                    status_chip("ADMIN"),
                                    status_chip("TEMPLATE_OWNER"),
                                    status_chip("OPERATOR"),
                                    status_chip("VIEWER"),
                                    status_chip("RETAINED", label="Còn · 3,2 MB"),
                                    status_chip("PURGED"),
                                ],
                                gap="xs",
                            ),
                        ],
                        withBorder=True,
                        p="lg",
                        radius="md",
                    ),
                    # 2. Buttons
                    dmc.Paper(
                        [
                            dmc.Title("2. Button (primary, danger, subtle)", order=4, mb="md"),
                            dmc.Group(
                                [
                                    button_primary("Lưu cấu hình", icon="lucide:save"),
                                    button_danger("Xóa dữ liệu", icon="lucide:trash-2"),
                                    button_subtle("Hủy bỏ"),
                                    button_primary("Đang xử lý", loading=True),
                                    button_danger("Đã khóa", disabled=True),
                                ],
                                gap="md",
                            ),
                        ],
                        withBorder=True,
                        p="lg",
                        radius="md",
                    ),
                    # 3. KpiCards
                    dmc.Paper(
                        [
                            dmc.Title("3. KpiCard", order=4, mb="md"),
                            dmc.SimpleGrid(
                                cols=3,
                                children=[
                                    kpi_card(
                                        "Tổng khớp",
                                        "184",
                                        tone="ok",
                                        meta="Tỷ lệ 92.0%",
                                        icon="lucide:check-circle-2",
                                    ),
                                    kpi_card(
                                        "Lệch giá trị",
                                        "4",
                                        tone="crit",
                                        meta="Độ lệch 15.420.000",
                                        icon="lucide:alert-circle",
                                    ),
                                    kpi_card(
                                        "Dung lượng tạm",
                                        "3,2 MB",
                                        tone="warn",
                                        meta="Ngưỡng cảnh báo: 2,0 GB",
                                        icon="lucide:database",
                                    ),
                                ],
                            ),
                        ],
                        withBorder=True,
                        p="lg",
                        radius="md",
                    ),
                    # 4. Form Fields
                    dmc.Paper(
                        [
                            dmc.Title("4. Field (nhãn, gợi ý, lỗi aria-describedby)", order=4, mb="md"),
                            dmc.SimpleGrid(
                                cols=2,
                                children=[
                                    form_field(
                                        dmc.TextInput(id="gal-input-user", placeholder="vd: nguyen.van.a"),
                                        label="Tên đăng nhập",
                                        hint="Chữ thường không dấu",
                                        required=True,
                                        field_id="gal-input-user",
                                    ),
                                    form_field(
                                        dmc.PasswordInput(id="gal-input-pwd", placeholder="Mật khẩu"),
                                        label="Mật khẩu ban đầu",
                                        error="Mật khẩu không được để trống",
                                        required=True,
                                        field_id="gal-input-pwd",
                                    ),
                                ],
                            ),
                        ],
                        withBorder=True,
                        p="lg",
                        radius="md",
                    ),
                    # 5. Alert
                    dmc.Paper(
                        [
                            dmc.Title("5. Alert", order=4, mb="md"),
                            dmc.Stack(
                                [
                                    alert_box(
                                        title="Thành công",
                                        message="Đã lưu cấu hình template thành công.",
                                        tone="ok",
                                    ),
                                    alert_box(
                                        title="Cảnh báo",
                                        message="Dung lượng tạm đạt 2.5 GB vượt ngưỡng khuyến nghị.",
                                        tone="warn",
                                    ),
                                    alert_box(
                                        title="Lỗi hệ thống",
                                        message="Không thể kết nối đến máy chủ Oracle qua VPN.",
                                        tone="crit",
                                        action=button_danger("Thử lại kết nối", size="xs"),
                                    ),
                                ],
                                gap="sm",
                            ),
                        ],
                        withBorder=True,
                        p="lg",
                        radius="md",
                    ),
                    # 6. EmptyState & FileDrop
                    dmc.Paper(
                        [
                            dmc.Title("6. EmptyState & FileDrop", order=4, mb="md"),
                            dmc.SimpleGrid(
                                cols=2,
                                children=[
                                    empty_state(
                                        title="Chưa có bản ghi nào",
                                        description="Hệ thống chưa tìm thấy dữ liệu phù hợp với bộ lọc hiện tại.",
                                        action=button_primary("Tạo mới", icon="lucide:plus"),
                                    ),
                                    file_drop(id="gal-file-drop"),
                                ],
                            ),
                        ],
                        withBorder=True,
                        p="lg",
                        radius="md",
                    ),
                    # 7. CodeBlock & Formatters
                    dmc.Paper(
                        [
                            dmc.Title("7. CodeBlock & Formatters", order=4, mb="md"),
                            code_block(
                                "SELECT invoice_no, amount, created_at\nFROM invoices\nWHERE status = 'PAID'",
                                language="sql",
                            ),
                            dmc.Divider(my="md"),
                            dmc.Group(
                                [
                                    dmc.Text(f"format_currency: {format_currency(Decimal('24114547250'))}", size="sm"),
                                    dmc.Text(f"format_number: {format_number(1234567)}", size="sm"),
                                    dmc.Text(f"format_datetime: {format_datetime(datetime.now())}", size="sm"),
                                    dmc.Text(f"format_bytes: {format_bytes(3355443)}", size="sm"),
                                ],
                                gap="xl",
                            ),
                        ],
                        withBorder=True,
                        p="lg",
                        radius="md",
                    ),
                    modal_confirm(
                        id="gal-modal-confirm",
                        title="Xác nhận xóa dữ liệu tạm",
                        description="Hành động này sẽ xóa dữ liệu tạm của các run đã chọn.",
                        confirm_text="XOA",
                    ),
                ],
                gap="lg",
                py="xl",
            )
        ],
        size="lg",
    )
