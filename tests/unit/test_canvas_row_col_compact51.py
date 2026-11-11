"""Task 51: cụm Hàng/Cột trên canvas không rớt hàng ở card hẹp — nhãn lên
trên ô nhập, ô nhập 36px, lề ngang card 6px.
"""

from __future__ import annotations


def _param(pid, row, span, label="Từ ngày", order=10):
    return {
        "id": pid,
        "code": f"p_{pid}",
        "label": label,
        "display_row": row,
        "grid_span": span,
        "display_order": order,
        "data_type": "DATE",
        "control_type": "DATE",
        "lov_type": "NONE",
        "required": True,
    }


def _first_card():
    import app.ui.pages.report_admin as page

    params = [_param(1, 1, 2, "Từ ngày", 10), _param(2, 1, 2, "Đến ngày", 20)]
    canvas = page._render_param_canvas(params, [])
    grid = canvas.children[0].children[1]
    return grid.children[0]


class TestRowColCompact:
    def test_inputs_width_36(self):
        card = _first_card()
        hc = card.children[2]
        row_stack, span_stack = hc.children
        assert getattr(row_stack.children[1], "w", None) == 36
        assert getattr(span_stack.children[1], "w", None) == 36

    def test_labels_above_inputs(self):
        card = _first_card()
        hc = card.children[2]
        row_stack, span_stack = hc.children
        assert type(row_stack).__name__ == "Stack"
        assert type(span_stack).__name__ == "Stack"
        assert row_stack.children[0].children == "Hàng"
        assert span_stack.children[0].children == "Cột"

    def test_card_horizontal_padding_6(self):
        card = _first_card()
        assert card.style.get("padding") == "6px 6px"
