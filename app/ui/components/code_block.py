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
    """Khối hiển thị mã / SQL với nút sao chép."""
    try:
        return dmc.CodeHighlight(
            code=code,
            language=language,
            copyLabel=copy_label,
            copiedLabel=copied_label,
            radius="md",
            **kwargs,
        )
    except Exception:
        return dmc.Code(
            code,
            block=True,
            **kwargs,
        )

