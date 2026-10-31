#!/usr/bin/env python3
"""Sinh app/ui/theme.py (theme dash-mantine-components) từ designs/tokens.json.

Chạy: python scripts/gen_dmc_theme.py (hoặc uv run poe theme). Không sửa tay file sinh ra.
Mỗi màu token mở rộng thành dải 10 sắc Mantine; sắc số 6 bằng đúng giá trị token.
"""

from __future__ import annotations

import json
import pprint
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
T = json.loads((ROOT / "designs" / "tokens.json").read_text(encoding="utf-8"))
OUT = ROOT / "app" / "ui" / "theme.py"


def _rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> str:
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def scale(base: str) -> list[str]:
    b = _rgb(base)
    light = [_mix((255, 255, 255), b, t) for t in (0.08, 0.18, 0.32, 0.48, 0.64, 0.82)]
    dark = [_mix(b, (0, 0, 0), t) for t in (0.15, 0.30, 0.45)]
    return [*light, base.upper(), *dark]


c, s, ty = T["color"], T["space"], T["type"]
theme = {
    "primaryColor": "primary",
    "primaryShade": {"light": 6, "dark": 4},
    "colors": {k: scale(c[k]["light"]) for k in ("primary", "ok", "crit", "warn", "purple", "off", "info")},
    "fontFamily": T["font"]["ui"],
    "fontFamilyMonospace": T["font"]["mono"],
    "defaultRadius": "md",
    "radius": {
        "xs": "4px",
        "sm": "6px",
        "md": f"{T['radius']['radius-control']}px",
        "lg": f"{T['radius']['radius-card']}px",
        "xl": "16px",
    },
    "spacing": {
        "xs": f"{s['space-6']}px",
        "sm": f"{s['space-10']}px",
        "md": f"{s['space-16']}px",
        "lg": f"{s['space-24']}px",
        "xl": f"{s['space-32']}px",
    },
    "fontSizes": {
        "xs": f"{ty['chip']['size']}px",
        "sm": f"{ty['body-sm']['size']}px",
        "md": f"{ty['body']['size']}px",
        "lg": f"{ty['section-title']['size']}px",
        "xl": f"{ty['screen-title']['size']}px",
    },
    "headings": {"fontFamily": T["font"]["ui"], "fontWeight": "700"},
    "other": {"status": T["status"]},
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(
    '"""SINH RA bởi scripts/gen_dmc_theme.py từ designs/tokens.json. Không sửa tay."""\n\nTHEME = '
    + pprint.pformat(theme, width=110, sort_dicts=False)
    + "\n",
    encoding="utf-8",
)
print(f"Đã sinh {OUT.relative_to(ROOT)}")

ASSETS = ROOT / "app" / "ui" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
tokens_css = ROOT / "designs" / "tokens.css"
if tokens_css.exists():
    (ASSETS / "tokens.css").write_text(tokens_css.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Đã sao chép tokens.css vào {ASSETS.relative_to(ROOT)}")
