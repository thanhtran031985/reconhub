from __future__ import annotations

from typing import Any

ROW_HEIGHT: int = 32
HEADER_HEIGHT: int = 34

DEFAULT_COL_DEF: dict[str, Any] = {
    "sortable": True,
    "filter": True,
    "resizable": True,
    "floatingFilter": False,
    "minWidth": 80,
}

DIFF_CELL_CLASS_RULES: dict[str, str] = {
    "rh-diff": "params.value != null && params.data && (params.data.has_diff === true || params.data.status === 'DIFF')",
    "rh-diff-num": "params.value != null && params.data && params.data.diff_amount != null && params.data.diff_amount !== 0",
}

GRID_DEFAULTS: dict[str, Any] = {
    "rowHeight": ROW_HEIGHT,
    "headerHeight": HEADER_HEIGHT,
    "animateRows": False,
    "suppressCellFocus": True,
    "defaultColDef": DEFAULT_COL_DEF,
}

