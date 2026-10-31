import dash
from dash import html
import dash_mantine_components as dmc

dash.register_page(__name__, path="/", title="ReconHub")

layout = dmc.Container(
    dmc.Stack(
        [
            dmc.Title("ReconHub", order=2),
            dmc.Text("Hệ thống đối soát dữ liệu Excel và Oracle", c="dimmed"),
        ],
        gap="md",
        p="xl",
    ),
    size="lg",
)
