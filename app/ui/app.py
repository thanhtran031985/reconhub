from __future__ import annotations

from pathlib import Path

import dash
import dash_mantine_components as dmc
from dash import Dash

from app.core.config import get_settings
from app.routes.health import health_bp
from app.ui.theme import THEME

UI_DIR = Path(__file__).resolve().parent

settings = get_settings()

app = Dash(
    __name__,
    use_pages=True,
    pages_folder=str(UI_DIR / "pages"),
    assets_folder=str(UI_DIR / "assets"),
    title="ReconHub",
    update_title="",
    suppress_callback_exceptions=True,
)

server = app.server
server.secret_key = settings.FLASK_SECRET_KEY
server.register_blueprint(health_bp)

app.layout = dmc.MantineProvider(
    children=dash.page_container,
    theme=THEME,
)

if __name__ == "__main__":
    app.run(port=settings.DASH_PORT, debug=settings.DASH_DEBUG)
