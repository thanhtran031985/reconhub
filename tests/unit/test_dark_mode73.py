"""Tests task 73 — dark mode: token custom phải theo scheme của Mantine,
không còn màu chữ/nền cố định chìm ở dark mode.

- Bộ sinh token (scripts/design_system.py) phải dùng selector dark của
  Mantine `[data-mantine-color-scheme="dark"]`, không dùng
  `[data-theme="dark"]` (không code nào set data-theme — D1).
- File sinh ra designs/tokens.css + bản sao app/ui/assets/tokens.css
  phải đồng bộ và chứa selector Mantine.
- kpi_card: số liệu tone mặc định dùng màu ink thích ứng (var(--ink)),
  không dùng c="dark" cố định (D2); tone crit/warn giữ màu riêng.
- Rà toàn app/ui: không còn c="dark", không dùng biến CSS không tồn
  tại trong tokens.json (fallback sáng sẽ áp dụng cả ở dark mode),
  không còn hex nền/chữ sáng viết cứng (trừ ô SQL tối cố ý ở
  report_admin.py).
- D6: primaryShade dark = 5 (không phải 4) để nút filled chữ trắng
  đạt tương phản >= 3.8 ở dark mode.
- D7: AG Grid có biến --ag-* theo toggle dark của app (không theo
  prefers-color-scheme của OS) trong custom.css.
- D8: renderer trạng thái của grid Lịch sử báo cáo (dashAgGridFunctions.js)
  dùng token --ok/--crit/--info/--ink-soft, không dùng tên màu CSS cố định.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
UI = ROOT / "app" / "ui"
TOKENS_JSON = ROOT / "designs" / "tokens.json"
DESIGN_SYSTEM_PY = ROOT / "scripts" / "design_system.py"
TOKENS_CSS = ROOT / "designs" / "tokens.css"
ASSETS_TOKENS_CSS = ROOT / "app" / "ui" / "assets" / "tokens.css"

# Hex cố ý: ô nhập SQL ở report_admin.py là editor tối (nền #0a1427,
# chữ #dce8ff) — đọc được ở cả 2 mode, không phải lỗi.
ALLOWED_BARE_HEX = {("app/ui/pages/report_admin.py", "#0a1427"), ("app/ui/pages/report_admin.py", "#dce8ff")}


def _defined_vars() -> set[str]:
    t = json.loads(TOKENS_JSON.read_text(encoding="utf-8"))
    defined = set(t["color"]) | set(t["shadow"])
    defined |= {f"type-{k}-{s}" for k in t["type"] for s in ("size", "line", "weight")}
    defined |= set(t["space"]) | set(t["radius"]) | set(t["size"])
    defined |= {"font-ui", "font-mono"}
    return defined


def test_token_generator_uses_mantine_dark_selector() -> None:
    src = DESIGN_SYSTEM_PY.read_text(encoding="utf-8")
    assert '[data-mantine-color-scheme="dark"]' in src
    assert '[data-theme="dark"]' not in src
    assert '[data-theme="light"]' not in src


def test_generated_tokens_css_uses_mantine_dark_selector() -> None:
    css = TOKENS_CSS.read_text(encoding="utf-8")
    assert ":root {" in css
    assert "--bg: #F5F5F5;" in css  # light giữ nguyên
    assert '[data-mantine-color-scheme="dark"] {' in css
    assert "--bg: #1F1F1F;" in css  # dark có giá trị tối
    assert "[data-theme=" not in css


def test_assets_tokens_css_in_sync_with_designs() -> None:
    assert ASSETS_TOKENS_CSS.read_text(encoding="utf-8") == TOKENS_CSS.read_text(encoding="utf-8")


def _value_text_c(tone: str) -> str | None:
    from app.ui.components.kpi_card import kpi_card

    card = kpi_card("Tổng run", 420, tone=tone)
    stack = card.children
    value_text = stack.children[1]
    assert type(value_text).__name__ == "Text"
    return value_text.c


@pytest.mark.parametrize("tone", ["primary", "off", "info", "ok", "purple"])
def test_kpi_card_value_color_adapts_to_theme(tone: str) -> None:
    assert _value_text_c(tone) == "var(--ink)"


@pytest.mark.parametrize("tone", ["crit", "warn"])
def test_kpi_card_value_color_keeps_tone(tone: str) -> None:
    assert _value_text_c(tone) == tone


def _ui_py_files() -> list[Path]:
    return sorted(UI.rglob("*.py"))


def test_no_hardcoded_dark_text_color() -> None:
    bad: list[str] = []
    for path in _ui_py_files():
        text = path.read_text(encoding="utf-8")
        for pat in ('c="dark"', "c='dark'", 'else "dark"', "else 'dark'"):
            if pat in text:
                bad.append(f"{path.relative_to(ROOT)}: {pat}")
    assert not bad, bad


def test_no_undefined_css_vars() -> None:
    defined = _defined_vars()
    var_pat = re.compile(r"var\(--([a-zA-Z0-9_-]+)")
    bad: list[str] = []
    files = _ui_py_files() + [UI / "assets" / "custom.css"]
    for path in files:
        if path.name in ("theme.py", "tokens.css"):
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in var_pat.finditer(line):
                name = m.group(1)
                if name.startswith("mantine-"):
                    continue
                if name not in defined:
                    bad.append(f"{path.relative_to(ROOT)}:{i}: --{name}")
    assert not bad, bad


def test_no_bare_light_hex() -> None:
    hex_pat = re.compile(r"#[0-9a-fA-F]{3,6}\b")
    var_pat = re.compile(r"var\([^)]*\)")
    bad: list[str] = []
    files = _ui_py_files() + [UI / "assets" / "custom.css"]
    for path in files:
        if path.name in ("theme.py", "tokens.css"):
            continue
        rel = str(path.relative_to(ROOT))
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = var_pat.sub("", line)
            if line.strip().startswith("#"):
                continue
            for m in hex_pat.finditer(stripped):
                if (rel, m.group(0)) not in ALLOWED_BARE_HEX:
                    bad.append(f"{rel}:{i}: {m.group(0)} :: {line.strip()[:100]}")
    assert not bad, bad


def test_primary_shade_dark_is_5() -> None:
    """D6: nút filled primary ở dark mode dùng shade 5 (#3A86C9),
    chữ trắng đạt tương phản ~3.9 (shade 4 #65A1D5 chỉ đạt 2.76)."""
    gen = (ROOT / "scripts" / "gen_dmc_theme.py").read_text(encoding="utf-8")
    assert '"primaryShade": {"light": 6, "dark": 5}' in gen
    theme = (ROOT / "app" / "ui" / "theme.py").read_text(encoding="utf-8")
    assert "'primaryShade': {'light': 6, 'dark': 5}" in theme


def test_ag_grid_dark_vars_follow_app_scheme() -> None:
    """D7: grid tối theo toggle của app, không theo OS — các biến
    --ag-* nền/chữ/viền dưới selector dark của Mantine."""
    css = (UI / "assets" / "custom.css").read_text(encoding="utf-8")
    assert '[data-mantine-color-scheme="dark"] .ag-theme-quartz-auto-dark' in css
    assert "--ag-background-color: var(--surface);" in css
    assert "--ag-foreground-color: var(--ink);" in css
    assert "--ag-header-background-color: var(--surface-2);" in css
    assert "--ag-border-color: var(--line);" in css


def test_grid_status_cell_uses_theme_tokens() -> None:
    """D8: màu trạng thái trong renderer JS của grid Lịch sử báo cáo
    dùng token thích ứng, không dùng tên màu CSS cố định ('green' chìm
    ở dark mode, tương phản 2.83). Lưu ý: 'red' ở mk('delete', ...)
    là prop color của DMC Button (Mantine tự thích ứng) — không động."""
    js = (UI / "assets" / "dashAgGridFunctions.js").read_text(encoding="utf-8")
    assert "DONE: 'var(--ok)'" in js
    assert "FAILED: 'var(--crit)'" in js
    assert "RUNNING: 'var(--info)'" in js
    assert "QUEUED: 'var(--ink-soft)'" in js
    assert "DONE: 'green'" not in js
    assert "FAILED: 'red'" not in js
    assert "RUNNING: 'blue'" not in js
