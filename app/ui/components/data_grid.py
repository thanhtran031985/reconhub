from __future__ import annotations

from typing import Any

import dash_ag_grid as dag
import dash_mantine_components as dmc

from app.ui.components.grid_defaults import (
    GRID_DEFAULTS,
)


def data_grid(
    id: str,
    columnDefs: list[dict[str, Any]],
    rowData: list[dict[str, Any]] | None = None,
    rowModelType: str = "clientSide",
    dashGridOptions: dict[str, Any] | None = None,
    className: str = "ag-theme-quartz-auto-dark",
    style: dict[str, Any] | None = None,
    container_style: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dmc.Box:
    """Wrapper cho dag.AgGrid định nghĩa sẵn Fluent Compact defaults (32px row, 34px header)."""
    options = dict(GRID_DEFAULTS)
    options["rowModelType"] = rowModelType
    if dashGridOptions:
        merged_options = {**options, **dashGridOptions}
        if "defaultColDef" in dashGridOptions and "defaultColDef" in options:
            merged_options["defaultColDef"] = {
                **options["defaultColDef"],
                **dashGridOptions["defaultColDef"],
            }
        options = merged_options

    grid_style: dict[str, Any] = {
        "height": "100%",
        "width": "100%",
        "minHeight": 0,
    }
    if style:
        grid_style.update(style)

    grid = dag.AgGrid(
        id=id,
        columnDefs=columnDefs,
        rowData=rowData,
        dashGridOptions=options,
        className=className,
        style=grid_style,
        **kwargs,
    )

    box_style: dict[str, Any] = {
        "flex": 1,
        "height": "100%",
        "minHeight": 0,
        "width": "100%",
        "display": "flex",
        "flexDirection": "column",
    }
    if container_style:
        box_style.update(container_style)

    return dmc.Box(grid, style=box_style)

