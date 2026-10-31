#!/usr/bin/env python3
"""Sinh designs/tokens.css và docs/DESIGN_SYSTEM.md từ designs/tokens.json + designs/README.md.

Chạy: python scripts/design_system.py  (hoặc uv run poe design-system). Không sửa tay file sinh ra.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
t = json.loads((ROOT / "designs" / "tokens.json").read_text(encoding="utf-8"))
guide = re.sub(r"^# .*\n", "", (ROOT / "designs" / "README.md").read_text(encoding="utf-8"), count=1)

css = [':root, [data-theme="light"] {', f"  --font-ui: {t['font']['ui']};", f"  --font-mono: {t['font']['mono']};"]
css += [f"  --{k}: {v['light']};" for k, v in t["color"].items()]
for k, v in t["type"].items():
    css += [f"  --type-{k}-size: {v['size']}px;", f"  --type-{k}-line: {v['line']};", f"  --type-{k}-weight: {v['weight']};"]
for grp in ("space", "radius", "size"):
    css += [f"  --{k}: {v}px;" for k, v in t[grp].items()]
css += [f"  --{k}: {v['light']};" for k, v in t["shadow"].items()]
css += ["  --motion-fast: 150ms;", "}", '[data-theme="dark"] {']
css += [f"  --{k}: {v['dark']};" for k, v in t["color"].items()]
css += [f"  --{k}: {v['dark']};" for k, v in t["shadow"].items()]
css += ["}", "@media (prefers-reduced-motion: reduce) { :root { --motion-fast: 0ms; } }"]
(ROOT / "designs" / "tokens.css").write_text("/* SINH TỪ tokens.json – không sửa tay */\n" + "\n".join(css) + "\n", encoding="utf-8")

md = [f"# {t['meta']['name']} — Design System", "",
      "Nguồn duy nhất cho màu, chữ, khoảng cách, bo góc, bóng, kích thước. **Không viết cứng hex, px trong page/component**: dùng biến CSS (`designs/tokens.css`, nạp vào `app/ui/assets/`) hoặc theme Dash Mantine (`app/ui/theme.py`, sinh bởi `scripts/gen_dmc_theme.py`). Thiếu token: thêm vào `designs/tokens.json` rồi chạy lại script.", "",
      f"Tệp này SINH RA bởi `python scripts/design_system.py`; không sửa tay. Phiên bản token: {t['version']}. {t['meta']['note']}", "",
      "---", "", "## 1. Nguyên tắc (từ designs/README.md)", "", re.sub(r"^## ", "### ", guide, flags=re.M), "",
      "## 2. Màu", "", "| Token | Giá trị | Dùng cho |", "|---|---|---|"]
md += [f"| `{k}` | Sáng `{v['light']}` · Tối `{v['dark']}` | {v['use']} |" for k, v in t["color"].items()]
md += ["", "### Trạng thái kết quả", "", "| Mã | Tone | Nhãn | Icon (lucide) |", "|---|---|---|---|"]
md += [f"| `{k}` | `{v[0]}` | {v[1]} | {v[2]} |" for k, v in t["status"].items()]
md += ["", "## 3. Chữ", "", f"- `--font-ui`: {t['font']['ui']}", f"- `--font-mono`: {t['font']['mono']}", "", "| Kiểu | Cỡ | Dòng | Đậm | Dùng cho |", "|---|---|---|---|---|"]
md += [f"| `{k}` | {v['size']}px | {v['line']} | {v['weight']} | {v['use']} |" for k, v in t["type"].items()]
for title, grp in (("4. Khoảng cách", "space"), ("5. Bo góc", "radius"), ("6. Kích thước", "size")):
    md += ["", f"## {title}", "", "| Token | Giá trị |", "|---|---|"] + [f"| `{k}` | `{v}px` |" for k, v in t[grp].items()]
md += ["", "## 7. Bóng", "", "| Token | Giá trị |", "|---|---|"] + [f"| `{k}` | Sáng `{v['light']}` · Tối `{v['dark']}` |" for k, v in t["shadow"].items()]
md += ["", "## 8. Dùng trong mã", "", "- Biến CSS: `var(--primary)`, `var(--space-12)`, `var(--radius-card)`.",
       "- Dash Mantine: `color=\"primary\"`, `p=\"md\"`, `radius=\"md\"`; dải màu ok/crit/warn/purple/off/info có trong theme.",
       "- Cách chuyển thiết kế: rule `.agents/rules/ui-dash.md` và bảng ánh xạ ở `designs/README.md`.", ""]
(ROOT / "docs" / "DESIGN_SYSTEM.md").write_text("\n".join(md), encoding="utf-8")
print("Đã sinh designs/tokens.css và docs/DESIGN_SYSTEM.md")
