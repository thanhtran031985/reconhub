from __future__ import annotations

from dash import Dash


def test_theme_tokens() -> None:
    from app.ui.theme import THEME

    assert THEME["primaryColor"] == "primary"
    assert "colors" in THEME
    expected_colors = {"primary", "ok", "crit", "warn", "purple", "off", "info"}
    assert set(THEME["colors"].keys()) == expected_colors
    for color_name, shades in THEME["colors"].items():
        assert len(shades) == 10, f"Màu {color_name} phải có đúng 10 sắc Mantine"


def test_dash_app_initialization() -> None:
    from app.ui.app import app

    assert isinstance(app, Dash)
    assert app.title == "ReconHub"
    assert app.layout is not None


def test_health_route() -> None:
    from app.wsgi import server

    with server.test_client() as client:
        res = client.get("/health")
        assert res.status_code == 200
        data = res.get_json()
        assert data is not None
        assert data.get("status") == "ok"
        assert data.get("db") == "up"
