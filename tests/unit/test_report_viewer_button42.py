"""Task 42: nút 'Xem báo cáo' cao bằng ô nhập tham số.

Nút Xem size='xs' (30px) trong khi các ô nhập mặc định size='sm' (36px)
nên nhìn thấp hơn 6px dù đã alignSelf end. Đổi nút sang size='sm'.
"""

from __future__ import annotations

from tests.unit.test_page_report_viewer import (
    _find_by_id,
    export_env,
    operator_ctx,
    run_env,
)

__all__ = ["export_env", "operator_ctx", "run_env"]


def test_run_button_size_matches_inputs(export_env, operator_ctx, monkeypatch):
    import app.ui.pages.report_viewer as page

    monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
    comp = page.layout(report_id=export_env["report_id"])
    btn = _find_by_id(comp, "viewer-run-btn")
    assert btn is not None
    assert btn.size == "sm"


def test_param_inputs_default_to_sm_size():
    import app.ui.pages.report_viewer as page

    base = {
        "id": 1,
        "code": "p_x",
        "label": "X",
        "required": False,
        "grid_span": 3,
        "lov": {"lov_type": "NONE"},
    }
    date_c = page.render_param_control({**base, "data_type": "DATE", "control_type": "DATE"}, None)
    # Không đặt size tường minh → Mantine mặc định "sm" (36px).
    assert getattr(date_c, "size", None) in (None, "sm")
    sel_c = page.render_param_control(
        {**base, "data_type": "STRING", "control_type": "SELECT",
         "lov": {"lov_type": "STATIC", "static_values": [["A", "Mục A"]]}},
        None,
    )
    assert getattr(sel_c, "size", None) in (None, "sm")
