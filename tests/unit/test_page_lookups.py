"""Tests cho màn hình Quản lý Lookups (/lookups)."""
from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine

from app.core.context import Ctx, Role


@pytest.fixture()
def lookups_env(tmp_path: Any, monkeypatch: Any) -> Any:
    """Fixture DB + monkeypatch service cho test trang lookups."""
    db_path = tmp_path / "lookups_page_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    import app.services.lookup as lookup_mod
    from app.db.metadata import metadata

    metadata.create_all(engine)
    monkeypatch.setattr("app.db.engine.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: engine)
    lookup_mod._lookup_cache.clear()

    # Seed dữ liệu
    with engine.begin() as conn:
        lookup_mod.ensure_default_lookup_data(conn)

    yield engine

    lookup_mod._lookup_cache.clear()


def _admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])


def _viewer_ctx() -> Ctx:
    return Ctx(user_id=2, username="viewer", full_name="Viewer", roles=[Role.VIEWER])


class TestLayoutRender:
    def test_layout_renders_without_error(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Layout /lookups phải render thành công khi đã đăng nhập."""
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout
        result = layout()
        assert result is not None

    def test_layout_has_screen12_search_inputs(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Layout phải có ô tìm kiếm Type và ô tìm kiếm Code theo chuẩn Screen12."""
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout
        result = str(layout())
        assert "lookups-type-search-input" in result
        assert "lookups-code-search-input" in result
        assert "lookups-code-active-filter" in result
        assert "lookups-edit-type-btn" in result
        assert "lookups-policy-alert" in result

    def test_layout_redirects_when_not_logged_in(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Layout redirect khi chưa đăng nhập."""
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: None)
        from app.ui.pages.lookups import layout
        result = layout()
        result_str = str(result)
        assert "forbidden" in result_str or "login" in result_str.lower() or "Location" in result_str

    def test_layout_contains_lookup_type_list(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Layout phải có vùng hiển thị danh sách Lookup Type."""
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout
        result = str(layout())
        assert "lookups-type-list" in result or "LOOKUP_TYPE" in result or "lookups" in result.lower()

    def test_layout_has_add_type_button(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Admin thấy nút Thêm loại danh mục."""
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout
        result = str(layout())
        assert "lookups-add-type-btn" in result


class TestRenderTypeList:
    def test_render_type_list_shows_seeded_types(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Hàm render_type_list hiển thị đủ Type sau khi seed."""
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_type_list
        ctx = _admin_ctx()
        result = str(render_type_list(ctx))
        assert "ISSUE_STATUS" in result or "Trạng thái đối soát" in result

    def test_render_type_list_shows_code_count_badge(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Mỗi type phải có badge đếm số code."""
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_type_list
        ctx = _admin_ctx()
        result = str(render_type_list(ctx))
        # ISSUE_STATUS có 4 code → badge phải hiển thị 4
        assert "4" in result


class TestRenderCodeTable:
    def test_render_code_table_shows_codes(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Bảng Giá trị phải hiển thị đủ mã ISSUE_STATUS."""
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_code_table
        ctx = _admin_ctx()
        result = str(render_code_table(ctx, lookup_type="ISSUE_STATUS"))
        assert "OPEN" in result
        assert "RESOLVED" in result

    def test_render_code_table_empty_when_no_type(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Bảng Giá trị trả empty state khi không có type."""
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_code_table
        ctx = _admin_ctx()
        result = str(render_code_table(ctx, lookup_type=None))
        assert result is not None


class TestHandleSelectType:
    def test_select_type_loads_code_table(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Click vào type trái → cập nhật bảng code bên phải."""
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import handle_select_type
        # Gọi callback trực tiếp
        result = handle_select_type("ISSUE_STATUS")
        # Phải trả tuple (code_table_ui, selected_store)
        assert result is not None
        assert len(result) == 2
        code_table, store = result
        assert code_table is not None
        assert store == "ISSUE_STATUS"



class TestUiUxFixes:
    def test_warn_color_is_selectable(self) -> None:
        from app.ui.pages.lookups import BADGE_COLORS

        assert "warn" in BADGE_COLORS

    def test_live_badge_preview_uses_new_values(self) -> None:
        from app.ui.pages.lookups import _live_badge_preview

        result = str(_live_badge_preview("Đang kiểm tra", "teal", "lucide:loader"))
        assert "Đang kiểm tra" in result
        assert "teal" in result
        assert "lucide:loader" in result

    def test_code_table_error_is_not_empty_state(self, lookups_env: Any, monkeypatch: Any) -> None:
        from app.schemas.errors import ErrorCode, ServiceResult
        from app.ui.pages.lookups import render_code_table

        monkeypatch.setattr(
            "app.ui.pages.lookups.list_lookup_codes",
            lambda ctx, lookup_type: ServiceResult.fail(ErrorCode.INTERNAL_ERROR, "DB lỗi"),
        )
        result = str(render_code_table(_admin_ctx(), lookup_type="ISSUE_STATUS"))
        assert "Không tải được danh sách mã" in result
        assert "Thử lại" in result
        assert "Chưa có giá trị nào" not in result

    def test_system_delete_button_is_disabled(self, lookups_env: Any, monkeypatch: Any) -> None:
        from app.ui.pages.lookups import render_code_table

        result = str(render_code_table(_admin_ctx(), lookup_type="ISSUE_STATUS"))
        # Mã hệ thống OPEN phải có nút xóa bị disabled, không chỉ đổi con trỏ.
        assert "Mã hệ thống, không thể xóa mã OPEN" in result


class TestLeftColumnDesign:
    def test_type_card_shows_total_and_active_counts(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import render_type_list

        ui, _total = render_type_list(_admin_ctx(), selected_type="ISSUE_REASON")
        text = str(ui)
        # Seed: ISSUE_REASON có 6 mã, đều đang dùng.
        assert "6 giá trị" in text
        assert "6 đang dùng" in text
        assert "ISSUE_REASON" in text

    def test_add_type_button_is_at_bottom_of_left_column(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout

        text = str(layout())
        assert "lookups-add-type-btn" in text
        assert "Thêm loại danh mục" in text
        assert "Tìm loại danh mục" in text


class TestDeleteModalCallbackIds83:
    """Task 83 (lỗi thật tìm ra khi check live): callback xóa phải tham chiếu
    đúng id nút của modal_confirm ({id}-cancel / {id}-confirm), không phải
    {id}-cancel-btn / {id}-confirm-btn — sai id làm Dash văng ReferenceError
    và modal xóa không bao giờ mở."""

    def test_delete_callback_string_inputs_exist_in_layout(self, lookups_env: Any, monkeypatch: Any) -> None:
        import dash._callback as cbmod

        from app.ui.pages.lookups import layout

        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        node = layout()
        layout_ids = {getattr(c, "id", None) for c in _walk(node) if isinstance(getattr(c, "id", None), str)}
        entry = next(e for e in cbmod.GLOBAL_CALLBACK_LIST if "lookups-delete-code-modal.opened" in e["output"])
        # Registry lưu input dạng dict {"id": ..., "property": ...}; id
        # pattern-matching lưu dạng chuỗi JSON -> loại khỏi id thường.
        input_ids = [(inp.get("id") if isinstance(inp, dict) else getattr(inp, "id", None)) for inp in entry["inputs"]]
        input_ids = [i for i in input_ids if isinstance(i, str) and not i.startswith("{")]
        assert "lookups-delete-code-modal-cancel" in input_ids
        assert "lookups-delete-code-modal-confirm" in input_ids
        missing = [i for i in input_ids if i not in layout_ids]
        assert not missing, f"callback xóa tham chiếu id không có trong layout: {missing}"

    def _mock_ctx(self, monkeypatch: Any, prop_id: str, value: Any) -> None:
        from types import SimpleNamespace

        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered=[{"prop_id": prop_id, "value": value}]),
        )

    def test_delete_click_opens_modal(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import cb_delete_code_modal

        self._mock_ctx(
            monkeypatch,
            '{"type": "lookups-delete-code-btn", "index": "ISSUE_REASON|EXTRA"}.n_clicks',
            1,
        )
        opened, target, _alert = cb_delete_code_modal([1], None, None, None)
        assert opened is True
        assert target == {"lookup_type": "ISSUE_REASON", "lookup_code": "EXTRA"}

    def test_delete_click_guard_no_click(self, lookups_env: Any, monkeypatch: Any) -> None:
        import dash.exceptions
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import cb_delete_code_modal

        self._mock_ctx(
            monkeypatch,
            '{"type": "lookups-delete-code-btn", "index": "ISSUE_REASON|EXTRA"}.n_clicks',
            None,
        )
        with pytest.raises(dash.exceptions.PreventUpdate):
            cb_delete_code_modal([None], None, None, None)

    def test_edit_click_guard_no_click_prevents_update(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Nút Sửa remount với n_clicks=None/0 phải raise PreventUpdate để chặn loop."""
        import dash.exceptions
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import cb_edit_code_modal

        self._mock_ctx(
            monkeypatch,
            '{"type": "lookups-edit-code-btn", "index": "ISSUE_REASON|EXTRA"}.n_clicks',
            None,
        )
        with pytest.raises(dash.exceptions.PreventUpdate):
            cb_edit_code_modal([None], None, None, "Nhãn", 1, "blue", "lucide:circle", "", None)


def _walk(component: Any) -> Any:
    """Yield component + mọi hậu duệ (duyệt đệ quy children)."""
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


class TestCodeTableActionIcons83:
    """Task 83: icon Sửa/Xóa ở cột Thao tác không rớt hàng (size sm + Tooltip + nowrap)."""

    def test_action_icons_are_sm_not_xl(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_code_table

        table = render_code_table(_admin_ctx(), lookup_type="ISSUE_STATUS")
        icons = [c for c in _walk(table) if type(c).__name__ == "ActionIcon"]
        assert icons  # bảng phải có icon thao tác
        assert all(getattr(c, "size", None) == "sm" for c in icons)
        assert not [c for c in icons if getattr(c, "size", None) == "xl"]
        # Icon vẽ bên trong thu từ 18 → 16.
        inner = [getattr(c, "children", None) for c in icons]
        assert all(getattr(ch, "width", None) == 16 for ch in inner)

    def test_action_icons_have_tooltips_with_aria_labels(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_code_table

        table = render_code_table(_admin_ctx(), lookup_type="ISSUE_STATUS")
        found = set()
        for tip in [c for c in _walk(table) if type(c).__name__ == "Tooltip"]:
            child = tip.children
            assert type(child).__name__ == "ActionIcon"
            assert getattr(tip, "withArrow", None) is True
            found.add((tip.label, child.id.get("type"), child.id.get("index")))
        assert ("Sửa mã OPEN", "lookups-edit-code-btn", "ISSUE_STATUS|OPEN") in found
        assert ("Mã hệ thống, không thể xóa mã OPEN", "lookups-delete-code-btn", "ISSUE_STATUS|OPEN") in found
        # Id dict giữ nguyên để callback bám theo.
        assert ("Sửa mã RESOLVED", "lookups-edit-code-btn", "ISSUE_STATUS|RESOLVED") in found

    def test_non_system_delete_tooltip(self, lookups_env: Any, monkeypatch: Any) -> None:
        from app.schemas.errors import ServiceResult
        from app.ui.pages.lookups import render_code_table

        monkeypatch.setattr(
            "app.ui.pages.lookups.list_lookup_codes",
            lambda ctx, lookup_type: ServiceResult(
                ok=True,
                data=[
                    {
                        "lookup_code": "CUSTOM",
                        "meaning": "Tùy chỉnh",
                        "color_badge": "blue",
                        "icon_name": "lucide:circle",
                        "display_order": 1,
                        "is_active": "Y",
                        "is_system": "N",
                    }
                ],
            ),
        )
        table = render_code_table(_admin_ctx(), lookup_type="ISSUE_STATUS")
        found = {
            (tip.label, tip.children.id.get("type"), tip.children.id.get("index"))
            for tip in [c for c in _walk(table) if type(c).__name__ == "Tooltip"]
        }
        assert ("Xóa mã CUSTOM", "lookups-delete-code-btn", "ISSUE_STATUS|CUSTOM") in found

    def test_action_group_is_nowrap(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_code_table

        table = render_code_table(_admin_ctx(), lookup_type="ISSUE_STATUS")
        action_groups = [
            c
            for c in _walk(table)
            if type(c).__name__ == "Group"
            and any(
                type(d).__name__ == "ActionIcon"
                and isinstance(getattr(d, "id", None), dict)
                and d.id.get("type") in ("lookups-edit-code-btn", "lookups-delete-code-btn")
                for d in _walk(c)
            )
        ]
        assert action_groups  # mỗi hàng phải có Group nút thao tác
        assert all(getattr(g, "wrap", None) == "nowrap" for g in action_groups)


class TestStatusColumnNoOnOffText84:
    """Task 84: cột Trạng thái chỉ còn Switch, bỏ chữ "Bật"/"Tắt"."""

    def test_status_cell_has_switch_only(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_code_table

        table = render_code_table(_admin_ctx(), lookup_type="ISSUE_STATUS")
        switches = [c for c in _walk(table) if type(c).__name__ == "Switch"]
        assert switches  # mỗi hàng phải có Switch trạng thái
        assert all(getattr(s, "size", None) == "md" for s in switches)
        # Không còn text "Bật"/"Tắt" nào trong bảng.
        texts = [getattr(c, "children", None) for c in _walk(table) if type(c).__name__ == "Text"]
        assert not [t for t in texts if t in ("Bật", "Tắt")]
        # Group chứa Switch không còn Text con.
        for group in [c for c in _walk(table) if type(c).__name__ == "Group"]:
            children = getattr(group, "children", None) or []
            if any(type(ch).__name__ == "Switch" for ch in children if ch is not None):
                assert not [ch for ch in children if ch is not None and type(ch).__name__ == "Text"]


class TestDeleteTypeButton84:
    """Task 84: icon xóa loại ở góc phải mỗi thẻ loại (canh giữa dọc)."""

    def test_type_card_has_delete_icon(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_type_list

        node, _total = render_type_list(_admin_ctx())
        icons = [
            c
            for c in _walk(node)
            if type(c).__name__ == "ActionIcon"
            and isinstance(getattr(c, "id", None), dict)
            and c.id.get("type") == "lookups-delete-type-btn"
        ]
        assert len(icons) == 2  # 2 loại seed
        assert all(getattr(c, "size", None) == "sm" for c in icons)
        assert all(getattr(c, "color", None) == "crit" for c in icons)
        assert all(getattr(c, "variant", None) == "subtle" for c in icons)
        by_index = {c.id.get("index"): c for c in icons}
        # Loại hệ thống bị khóa, loại thường bấm được (cả 2 seed đều hệ thống
        # nên kiểm tra disabled theo is_sys: ISSUE_STATUS disabled).
        assert by_index["ISSUE_STATUS"].disabled is True
        assert by_index["ISSUE_REASON"].disabled is True

    def test_delete_type_tooltip_has_code_count(self, lookups_env: Any, monkeypatch: Any) -> None:
        from app.services.lookup import create_lookup_code, create_lookup_type

        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_type_list

        create_lookup_type(_admin_ctx(), lookup_type="TESTTYPE", type_name="Loại test")
        create_lookup_code(_admin_ctx(), lookup_type="TESTTYPE", lookup_code="T1", meaning="T1", display_order=1)
        create_lookup_code(_admin_ctx(), lookup_type="TESTTYPE", lookup_code="T2", meaning="T2", display_order=2)
        node, _total = render_type_list(_admin_ctx())
        found = {
            (tip.label, tip.children.id.get("index"))
            for tip in [c for c in _walk(node) if type(c).__name__ == "Tooltip"]
            if type(getattr(tip, "children", None)).__name__ == "ActionIcon"
            and isinstance(getattr(tip.children, "id", None), dict)
            and tip.children.id.get("type") == "lookups-delete-type-btn"
        }
        assert ("Loại hệ thống, không thể xóa loại Trạng thái đối soát (ISSUE_STATUS)", "ISSUE_STATUS") in found
        assert ("Loại hệ thống, không thể xóa loại Nguyên nhân chênh lệch (ISSUE_REASON)", "ISSUE_REASON") in found
        # Loại thường: tooltip mang số mã sẽ bị xóa cùng.
        assert ("Xóa loại Loại test (TESTTYPE) — 2 mã", "TESTTYPE") in found

    def test_delete_icon_is_sibling_of_select_button(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Icon xóa nằm ngoài nút chọn (sibling) nên bấm xóa không chọn loại."""
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_type_list

        node, _total = render_type_list(_admin_ctx())
        groups = []
        for group in [c for c in _walk(node) if type(c).__name__ == "Group"]:
            children = [ch for ch in (getattr(group, "children", None) or []) if ch is not None]
            has_select = any(
                type(ch).__name__ == "Button"
                and isinstance(getattr(ch, "id", None), dict)
                and ch.id.get("type") == "lookups-type-item"
                for ch in children
            )
            has_delete = any(
                type(ch).__name__ == "Tooltip"
                and type(getattr(ch, "children", None)).__name__ == "ActionIcon"
                and isinstance(getattr(ch.children, "id", None), dict)
                and ch.children.id.get("type") == "lookups-delete-type-btn"
                for ch in children
            )
            if has_select and has_delete:
                groups.append(group)
        assert len(groups) == 2  # mỗi thẻ loại có 1 Group [nút chọn + icon xóa]
        assert all(getattr(g, "align", None) == "center" for g in groups)
        assert all(getattr(g, "wrap", None) == "nowrap" for g in groups)

    def test_layout_has_delete_type_modal_and_store(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout

        result = str(layout())
        assert "lookups-delete-type-modal" in result
        assert "lookups-delete-type-target-store" in result


class TestDeleteTypeModal84:
    """Task 84: callback xóa loại — đúng id modal_confirm (bài học task 83)."""

    def _mock_ctx(self, monkeypatch: Any, prop_id: str, value: Any) -> None:
        from types import SimpleNamespace

        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered=[{"prop_id": prop_id, "value": value}]),
        )

    def test_no_duplicate_callback_outputs(self) -> None:
        """Hồi quy: Output dùng chung bởi >1 callback phải có allow_duplicate.

        Không có allow_duplicate, Dash reject toàn bộ callback map và app
        render trắng (lỗi chỉ thấy ở check live, unit test thường không bắt).
        Kiểm tra TĨNH trên source của lookups.py thay vì GLOBAL_CALLBACK_LIST:
        list đó là process-global và create_app() đăng ký lại toàn bộ
        callback mỗi lần gọi (đã chứng minh: gọi 2 lần → lookups-code-table
        có 3–4 entry), nên đếm ở đó phụ thuộc lịch sử tiến trình và fail
        giả trong full suite.
        """
        import ast
        from collections import Counter
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent.parent / "app" / "ui" / "pages" / "lookups.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        plain: Counter[str] = Counter()
        dup_marked: Counter[str] = Counter()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and getattr(dec.func, "id", None) == "callback"):
                    continue
                for arg in dec.args:
                    if not (isinstance(arg, ast.Call) and getattr(arg.func, "id", None) == "Output"):
                        continue
                    if len(arg.args) < 2 or not all(isinstance(a, ast.Constant) for a in arg.args[:2]):
                        continue
                    base = f"{arg.args[0].value}.{arg.args[1].value}"
                    allow_dup = any(
                        kw.arg == "allow_duplicate" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                        for kw in arg.keywords
                    )
                    (dup_marked if allow_dup else plain)[base] += 1
        for base, n in plain.items():
            total = n + dup_marked[base]
            assert total <= 1 or n <= 1, (
                f"Output {base} dùng bởi {total} callback nhưng chỉ "
                f"{dup_marked[base]} có allow_duplicate (cần tối đa 1 callback không đánh dấu)"
            )
        # Cụ thể task 84: lookups-page-alert.children chia sẻ bởi 2 callback xóa.
        assert plain["lookups-page-alert.children"] == 1
        assert dup_marked["lookups-page-alert.children"] == 1

    def test_delete_type_callback_string_inputs_exist_in_layout(self, lookups_env: Any, monkeypatch: Any) -> None:
        import dash._callback as cbmod

        from app.ui.pages.lookups import layout

        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        node = layout()
        layout_ids = {getattr(c, "id", None) for c in _walk(node) if isinstance(getattr(c, "id", None), str)}
        entry = next(e for e in cbmod.GLOBAL_CALLBACK_LIST if "lookups-delete-type-modal.opened" in e["output"])
        input_ids = [(inp.get("id") if isinstance(inp, dict) else getattr(inp, "id", None)) for inp in entry["inputs"]]
        input_ids = [i for i in input_ids if isinstance(i, str) and not i.startswith("{")]
        assert "lookups-delete-type-modal-cancel" in input_ids
        assert "lookups-delete-type-modal-confirm" in input_ids
        assert "lookups-delete-type-modal-cancel-btn" not in input_ids
        assert "lookups-delete-type-modal-confirm-btn" not in input_ids
        missing = [i for i in input_ids if i not in layout_ids]
        assert not missing, f"callback xóa loại tham chiếu id không có trong layout: {missing}"

    def test_delete_type_click_opens_modal(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import cb_delete_type_modal

        self._mock_ctx(
            monkeypatch,
            '{"type": "lookups-delete-type-btn", "index": "DELTYPE"}.n_clicks',
            1,
        )
        opened, target, _alert = cb_delete_type_modal([1], None, None, None)
        assert opened is True
        assert target == {"lookup_type": "DELTYPE"}

    def test_delete_type_click_guard_no_click(self, lookups_env: Any, monkeypatch: Any) -> None:
        import dash.exceptions
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import cb_delete_type_modal

        self._mock_ctx(
            monkeypatch,
            '{"type": "lookups-delete-type-btn", "index": "DELTYPE"}.n_clicks',
            None,
        )
        with pytest.raises(dash.exceptions.PreventUpdate):
            cb_delete_type_modal([None], None, None, None)

    def test_delete_type_confirm_removes_type(self, lookups_env: Any, monkeypatch: Any) -> None:
        from app.services.lookup import create_lookup_type, list_lookup_types

        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import cb_delete_type_modal

        create_lookup_type(_admin_ctx(), lookup_type="DELTYPE", type_name="Delete me")
        self._mock_ctx(monkeypatch, "lookups-delete-type-modal-confirm.n_clicks", 1)
        opened, target, _alert = cb_delete_type_modal(None, None, 1, {"lookup_type": "DELTYPE"})
        assert opened is False
        types = list_lookup_types(_admin_ctx())
        assert "DELTYPE" not in [t["lookup_type"] for t in types.data]

    def test_sync_clears_deleted_selection(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Loại đang chọn vừa bị xóa thì đồng bộ coi như chưa chọn (D6)."""
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import cb_master_detail_sync

        self._mock_ctx(monkeypatch, "lookups-refresh-store.data", 1)
        result = cb_master_detail_sync([], 1, "", "", "all", "GONE_TYPE")
        assert result[1] is None  # selected_type
        assert result[2] == "Chọn loại danh mục ở cột trái"  # header
