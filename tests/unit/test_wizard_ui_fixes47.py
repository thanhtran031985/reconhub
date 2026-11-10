"""Task 47: footer to hơn, bảng tham số bước 3 (gap 8px, STT giữa, click Mã đổi
indicator), canvas 12 cột cân đối."""

from __future__ import annotations

from types import SimpleNamespace

from tests.unit.test_page_report_admin import _draft_state, _fresh_state
from tests.unit.test_page_report_viewer import _dump
from tests.unit.test_report_run_execute import admin_ctx, run_env

__all__ = ["run_env", "admin_ctx"]


def _walk(component, parent=None):
    """Yield (component, parent) cho mọi node trong cây Dash."""
    yield component, parent
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            if child is None or isinstance(child, (str, int, float)):
                continue
            yield from _walk(child, component)
    elif children is not None and not isinstance(children, (str, int, float)):
        yield from _walk(children, component)


def _param(p_id, span=2, row=1, order=10):
    return {
        "id": p_id,
        "code": f"p_{p_id}",
        "label": f"Tham số {p_id}",
        "data_type": "STRING",
        "control_type": "TEXT",
        "required": False,
        "display_row": row,
        "display_order": order,
        "grid_span": span,
    }


class TestFooterBigger:
    def test_footer_buttons_bigger(self):
        """Task 47: nút Quay lại/Tiếp theo cao 36px (chuẩn sm), footer 48px."""
        import app.ui.pages.report_admin as page

        for step in (1, 4, 6):
            text = _dump(page._render_wizard_footer(step, _fresh_state()))
            # _dump: top-level props là JSON ("..."), component con là repr ('...').
            assert "'height': '36px'" in text, f"step {step}: nút chưa to lên"
            assert '"height": "48px"' in text, f"step {step}: footer chưa chứa nổi nút"
            assert "20px" not in text, f"step {step}: còn footer 20px cũ"
            assert "'height': '18px'" not in text and '"height": "18px"' not in text, f"step {step}: còn nút 18px cũ"


class TestStep3Table:
    def test_table_cell_gaps_8px(self, run_env, admin_ctx, monkeypatch):
        """Task 47: mọi ô body padding ngang 4px → nội dung 2 cột kề nhau cách 8px."""
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        tree = page.render_step_content(3, state)
        bodies = [c for c, _ in _walk(tree) if c.__class__.__name__ == "TableTbody"]
        assert bodies, "không tìm thấy TableTbody bước 3"
        tds = [c for c, _ in _walk(bodies[0]) if c.__class__.__name__ == "TableTd"]
        assert tds, "bảng tham số không có dòng nào"
        for td in tds:
            style = getattr(td, "style", None) or {}
            assert style.get("padding") == "4px 4px", f"ô chưa có padding 4px: {style!r}"

    def test_stt_centered_with_spinners(self, run_env, admin_ctx, monkeypatch):
        """Task 47: STT canh giữa nhưng giữ nút tăng/giảm (không hideControls)."""
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        tree = page.render_step_content(3, state)
        found = 0
        for comp, parent in _walk(tree):
            cid = getattr(comp, "id", None)
            if isinstance(cid, dict) and cid.get("type") == "admin-p-table-order":
                found += 1
                style = (getattr(parent, "style", None) or {}) if parent is not None else {}
                assert style.get("textAlign") == "center", f"ô STT chưa canh giữa: {style!r}"
        assert found >= 1, "không tìm thấy ô STT"
        assert "hideControls" not in _dump(tree), "STT mất nút tăng/giảm"


class TestParamSelectIndicator:
    def test_click_code_moves_indicator(self, run_env, admin_ctx, monkeypatch):
        """Task 47: click Mã ở dòng 2 thì indicator chuyển sang dòng 2 (không ở dòng đầu)."""
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        # Seed mặc định chỉ có 1 tham số → thêm tham số thứ 2 để click dòng 2.
        vid = int(state["version_id"])
        res = page.create_param(
            admin_ctx,
            vid,
            {
                "code": "p_two",
                "label": "Tham số 2",
                "data_type": "STRING",
                "control_type": "TEXT",
                "required": False,
                "default_type": "NONE",
                "default_value": None,
                "display_row": 1,
                "display_order": 20,
                "grid_span": 3,
                "is_visible": True,
                "lov_type": "NONE",
            },
        )
        assert res.ok, res.message
        ver = page._version_detail(admin_ctx, vid)
        params = ver.get("params", [])
        assert len(params) >= 2, f"chỉ có {len(params)} tham số, cần >= 2"
        target = params[1]
        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered_id={"type": "admin-param-select", "index": target["id"]}),
        )
        n_clicks = [0] * len(params)
        n_clicks[1] = 1
        title, _lov_type, _body, new_state, row_styles = page.handle_p_select_click(n_clicks, state)
        assert f"Setup LOV: {target['code']}" == title
        assert new_state["editing_param_id"] == int(target["id"])
        assert len(row_styles) == len(params)
        assert row_styles[1].get("backgroundColor") == "rgba(0, 120, 212, 0.06)"
        assert "0078D4" in str(row_styles[1].get("borderLeft"))
        assert row_styles[0].get("backgroundColor") == "transparent"


class TestCanvasProportional:
    def test_canvas_cards_span_width(self):
        """Task 47: lưới 12 cột minmax(0,1fr), card span N rộng N/12, không bị đội track."""
        import app.ui.pages.report_admin as page

        params = [_param(i, span=2, row=1, order=10 * i) for i in range(1, 5)]
        tree = page._render_param_canvas(params, [])
        text = _dump(tree)
        assert "'gridTemplateColumns': 'repeat(12, minmax(0, 1fr))'" in text
        boxes = [c for c, _ in _walk(tree) if getattr(c, "className", None) == "rh-drag-param"]
        assert len(boxes) == 4
        for box in boxes:
            style = box.style or {}
            assert style.get("gridColumn") == "span 2"
            assert style.get("minWidth") == 0
        # Card hẹp (span 2): nhóm Hàng/Cột được wrap để không bị cắt nội dung.
        # wrap là prop component (repr: wrap='wrap'), không nằm trong style dict.
        assert "wrap='wrap'" in text
