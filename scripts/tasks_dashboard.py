#!/usr/bin/env python3
"""Sinh docs/tasks/dashboard.html từ docs/tasks/README.md và các progress.md. Không sửa tay file sinh ra.

Chạy: python scripts/tasks_dashboard.py  (hoặc uv run poe tasks-dashboard). Chỉ dùng thư viện chuẩn.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "docs" / "tasks"
KNOWN = {"⬜": "todo", "🔄": "doing", "❓": "review", "⚠️": "diff", "❌": "missing", "✅": "done"}
LABEL = {"todo": "Chưa làm", "doing": "Đang làm", "review": "Chưa rà soát", "diff": "Khác task.md",
         "missing": "Thiếu", "done": "Xong", "unknown": "Không rõ"}


def status(s: str) -> str:
    s = s.strip()
    return next((v for k, v in KNOWN.items() if s.startswith(k)), "unknown")


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


rows = []
for line in (TASKS / "README.md").read_text(encoding="utf-8").splitlines():
    if not line.startswith("|") or "---" in line:
        continue
    c = cells(line)
    if len(c) < 5 or c[0] == "#":
        continue
    m = re.match(r"\[([^\]]+)\]\(([^)]+)\)\s*—?\s*(.*)", c[1])
    r = {"nn": c[0], "slug": m.group(1) if m else c[1], "title": m.group(3) if m else "",
         "status": status(c[2]), "raw": c[2], "deps": c[3], "branch": c[4], "steps": []}
    p = TASKS / r["slug"] / "progress.md"
    if p.exists():
        for pl in p.read_text(encoding="utf-8").splitlines():
            if re.match(r"^\|\s*\d+\s*\|", pl):
                s = cells(pl) + ["", "", "", ""]
                r["steps"].append({"n": s[0], "name": s[1], "status": status(s[2]), "date": s[3], "commit": s[4]})
    rows.append(r)

e = html.escape
cnt = lambda s: sum(1 for r in rows if r["status"] == s)  # noqa: E731
total = len(rows)
now = datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M")


def card(r: dict) -> str:
    done = sum(1 for s in r["steps"] if s["status"] == "done")
    pct = round(done * 100 / len(r["steps"])) if r["steps"] else 0
    warn = f'<div class="w">Ký hiệu trạng thái không hợp lệ: {e(r["raw"])}</div>' if r["status"] == "unknown" else ""
    steps = "".join(f'<tr><td>{e(s["n"])}</td><td>{e(s["name"])}</td><td><span class="chip s-{s["status"]}">{LABEL[s["status"]]}</span></td>'
                    f'<td>{e(s["date"])}</td><td><code>{e(s["commit"])}</code></td></tr>' for s in r["steps"])
    return (f'<details class="t s-{r["status"]}"><summary><span class="nn">{e(r["nn"])}</span><span class="nm"><b>{e(r["slug"])}</b>'
            f'<small>{e(r["title"])}</small></span><span class="chip s-{r["status"]}">{LABEL[r["status"]]}</span>'
            f'<span class="bar"><i style="width:{pct}%"></i></span><span class="sc">{done}/{len(r["steps"])}</span></summary>{warn}'
            f'<div class="meta">Phụ thuộc: {e(r["deps"])} · Nhánh: <code>{e(r["branch"])}</code> · <a href="{e(r["slug"])}/task.md">task.md</a> · '
            f'<a href="{e(r["slug"])}/progress.md">progress.md</a></div><table><tr><th>Bước</th><th>Nội dung</th><th>Trạng thái</th>'
            f'<th>Ngày</th><th>Commit</th></tr>{steps}</table></details>')


CSS = """body{font-family:"Segoe UI",Inter,Arial,sans-serif;margin:0;background:#F5F7FB;color:#1D2939;font-size:14px}
header{background:#0F1B33;color:#fff;padding:18px 28px}h1{margin:0;font-size:20px}header small{color:#CFD8EA}
main{padding:20px 28px;max-width:1200px}.kpis{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
.k{background:#fff;border:1px solid #E3E8F0;border-radius:12px;padding:12px 16px;min-width:130px}.k b{display:block;font-size:22px}
.t{background:#fff;border:1px solid #E3E8F0;border-left:4px solid #E3E8F0;border-radius:12px;margin-bottom:8px}
summary{display:flex;gap:12px;align-items:center;padding:10px 14px;cursor:pointer;list-style:none}
.nn{font-family:Consolas,monospace;font-weight:700;width:28px}.nm{flex:1;display:flex;flex-direction:column}.nm small{color:#667085}
.chip{padding:2px 8px;border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap}
.s-todo{background:#F2F4F7;color:#475467}.s-doing{background:#EAF1FF;color:#1D4ED8}.s-review{background:#F1EDFF;color:#5925DC}
.s-diff{background:#FFF4E5;color:#B54708}.s-missing{background:#FDECEC;color:#B42318}.s-done{background:#E8F8F0;color:#027A48}.s-unknown{background:#E3E8F0;color:#475467}
details.s-done{border-left-color:#12B76A}details.s-doing{border-left-color:#2563EB}details.s-missing{border-left-color:#E5484D}details.s-diff{border-left-color:#F79009}details.s-review{border-left-color:#7A5AF8}
details.t{background:#fff}.bar{width:120px;height:8px;background:#F2F4F7;border-radius:8px;overflow:hidden}.bar i{display:block;height:100%;background:#12B76A}
.sc{width:40px;text-align:right;color:#667085}.meta{padding:0 14px 8px;color:#667085}
table{width:calc(100% - 28px);margin:0 14px 14px;border-collapse:collapse}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #E3E8F0}
th{background:#F8FAFC;font-size:12px;color:#667085}.w{margin:0 14px 8px;padding:6px 10px;background:#FFF4E5;color:#B54708;border-radius:8px}
code{font-family:Consolas,monospace;font-size:12px}a{color:#2563EB}"""

doc = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ReconHub – Tiến độ task</title><style>{CSS}</style></head><body>
<header><h1>ReconHub – Tiến độ task</h1><small>Sinh lúc {now} bởi scripts/tasks_dashboard.py. Không sửa tay.</small></header>
<main><div class="kpis"><div class="k">Hoàn thành<b>{cnt('done')}/{total} ({round(cnt('done')*100/total) if total else 0}%)</b></div>
<div class="k">Đang làm<b>{cnt('doing')}</b></div><div class="k">Chưa rà soát<b>{cnt('review')}</b></div>
<div class="k">Khác task / Thiếu<b>{cnt('diff') + cnt('missing')}</b></div><div class="k">Chưa làm<b>{cnt('todo')}</b></div></div>
{''.join(card(r) for r in rows)}</main></body></html>"""
(TASKS / "dashboard.html").write_text(doc, encoding="utf-8")
print(f"dashboard.html: {total} task, {cnt('done')} xong")
