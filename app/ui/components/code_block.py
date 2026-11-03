from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc


def code_block(
    code: str,
    language: str = "sql",
    copy_label: str = "Sao chép",
    copied_label: str = "Đã sao chép",
    **kwargs: Any,
) -> Any:
    """Khối hiển thị mã / SQL với độ tương phản cao (chữ sáng trên nền tối)."""
    default_style = {
        "backgroundColor": "var(--code-bg, #0F1B33)",
        "color": "var(--code-ink, #D6E2FF)",
        "fontFamily": "var(--font-mono, 'JetBrains Mono', Consolas, monospace)",
        "borderRadius": "8px",
        "fontSize": "13px",
        "lineHeight": "1.5",
    }
    user_style = kwargs.pop("style", {})
    merged_style = {**default_style, **user_style}

    try:
        return dmc.CodeHighlight(
            code=code,
            language=language,
            copyLabel=copy_label,
            copiedLabel=copied_label,
            style=merged_style,
            **kwargs,
        )
    except Exception:
        return dmc.Code(
            code,
            block=True,
            style=merged_style,
            **kwargs,
        )
