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

    def test_layout_has_type_select_command_bar(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Layout có Select chọn loại ở command bar thay cho card trái (task 83)."""
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout
        result = str(layout())
        assert "lookups-type-select" in result
        assert "lookups-type-count-text" in result
        assert "lookups-code-search-input" in result
        assert "lookups-code-active-filter" in result
        assert "lookups-edit-type-btn" in result
        assert "lookups-policy-alert" in result
        assert "lookups-add-type-btn" in result
        # Card trái đã xóa: không còn danh sách loại / ô tìm loại.
        assert "lookups-type-list" not in result
        assert "lookups-type-search-input" not in result

    def test_layout_redirects_when_not_logged_in(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Layout redirect khi chưa đăng nhập."""
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: None)
        from app.ui.pages.lookups import layout
        result = layout()
        result_str = str(result)
        assert "forbidden" in result_str or "login" in result_str.lower() or "Location" in result_str

    def test_layout_contains_lookup_type_select(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Layout phải có Select chọn Lookup Type ở command bar (task 83)."""
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout
        result = str(layout())
        assert "lookups-type-select" in result
        assert "ISSUE_STATUS" in result or "Trạng thái đối soát" in result

    def test_layout_has_add_type_button(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Admin thấy nút Thêm loại danh mục."""
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout
        result = str(layout())
        assert "lookups-add-type-btn" in result


class TestBuildTypeOptions:
    def test_build_type_options_labels(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Option Select giữ thông tin card trái từng hiện: tên (CODE) — N giá trị · M đang dùng."""
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import build_type_options

        options, total = build_type_options(_admin_ctx())
        assert total == 2
        by_value = {o["value"]: o["label"] for o in options}
        assert by_value["ISSUE_STATUS"] == "Trạng thái đối soát (ISSUE_STATUS) — 4 giá trị · 4 đang dùng"
        assert by_value["ISSUE_REASON"] == "Nguyên nhân chênh lệch (ISSUE_REASON) — 6 giá trị · 6 đang dùng"

    def test_build_type_options_empty_on_error(self, lookups_env: Any, monkeypatch: Any) -> None:
        from app.schemas.errors import ErrorCode, ServiceResult
        from app.ui.pages.lookups import build_type_options

        monkeypatch.setattr(
            "app.ui.pages.lookups.list_lookup_types",
            lambda ctx: ServiceResult.fail(ErrorCode.INTERNAL_ERROR, "DB lỗi"),
        )
        options, total = build_type_options(_admin_ctx())
        assert options == []
        assert total == 0


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


class TestTypeSelectFlow83:
    """Task 83 (phần 2): chọn loại bằng Select ở command bar thay cho card trái."""

    def _mock_ctx(self, monkeypatch: Any, prop_id: str, value: Any) -> None:
        from types import SimpleNamespace

        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered=[{"prop_id": prop_id, "value": value}]),
        )

    def test_layout_no_left_column(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout

        text = str(layout())
        assert "lookups-type-select" in text
        assert "2 loại" in text
        assert "lookups-add-type-btn" in text
        assert "Chọn loại danh mục" in text
        assert "ở cột trái" not in text
        assert "lookups-type-list" not in text

    def test_select_type_via_callback_updates_table(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import cb_master_detail_sync

        self._mock_ctx(monkeypatch, "lookups-type-select.value", "ISSUE_STATUS")
        result = cb_master_detail_sync("ISSUE_STATUS", 0, "", "all", None)
        assert len(result) == 11
        (
            code_table,
            selected,
            header,
            badge,
            _badge_style,
            _add_disabled,
            _edit_disabled,
            _policy,
            options,
            value,
            count_text,
        ) = result
        assert selected == "ISSUE_STATUS"
        assert value == "ISSUE_STATUS"
        assert "Trạng thái đối soát" in header
        assert badge == "ISSUE_STATUS"
        assert "OPEN" in str(code_table)
        assert any(o["value"] == "ISSUE_STATUS" for o in options)
        assert count_text == "2 loại"

    def test_refresh_after_add_type_adds_option(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        monkeypatch.setattr("app.ui.pages.lookups.get_current_ctx", lambda: _admin_ctx())
        from app.services.lookup import create_lookup_type
        from app.ui.pages.lookups import cb_master_detail_sync

        res = create_lookup_type(_admin_ctx(), lookup_type="TEST83", type_name="Loại kiểm tra 83", description=None)
        assert res.ok
        self._mock_ctx(monkeypatch, "lookups-refresh-store.data", 1)
        result = cb_master_detail_sync(None, 1, "", "all", None)
        options = result[8]
        assert any(o["value"] == "TEST83" for o in options)
        assert result[10] == "3 loại"

    def test_empty_state_text_mentions_top_not_left(self, lookups_env: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import render_code_table

        text = str(render_code_table(_admin_ctx(), lookup_type=None))
        assert "ở trên" in text
        assert "ở cột trái" not in text


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
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: lookups_env)
        from app.ui.pages.lookups import cb_delete_code_modal

        self._mock_ctx(
            monkeypatch,
            '{"type": "lookups-delete-code-btn", "index": "ISSUE_REASON|EXTRA"}.n_clicks',
            None,
        )
        opened, target, _alert = cb_delete_code_modal([None], None, None, None)
        assert opened is False
        assert target is None


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
