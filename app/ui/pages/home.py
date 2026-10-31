import dash
import dash_mantine_components as dmc

dash.register_page(__name__, path="/", title="ReconHub")  # type: ignore[no-untyped-call]

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
