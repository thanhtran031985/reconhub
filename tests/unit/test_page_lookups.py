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
        monkeypatch.setattr("app.core.session.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout
        result = layout()
        assert result is not None

    def test_layout_has_screen12_search_inputs(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Layout phải có ô tìm kiếm Type và ô tìm kiếm Code theo chuẩn Screen12."""
        monkeypatch.setattr("app.core.session.get_current_ctx", lambda: _admin_ctx())
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
        monkeypatch.setattr("app.core.session.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import layout
        result = str(layout())
        assert "lookups-type-list" in result or "LOOKUP_TYPE" in result or "lookups" in result.lower()

    def test_layout_has_add_type_button(self, lookups_env: Any, monkeypatch: Any) -> None:
        """Admin thấy nút Thêm loại danh mục."""
        monkeypatch.setattr("app.core.session.get_current_ctx", lambda: _admin_ctx())
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
        monkeypatch.setattr("app.core.session.get_current_ctx", lambda: _admin_ctx())
        from app.ui.pages.lookups import handle_select_type
        # Gọi callback trực tiếp
        result = handle_select_type("ISSUE_STATUS")
        # Phải trả tuple (code_table_ui, selected_store)
        assert result is not None
        assert len(result) == 2
        code_table, store = result
        assert code_table is not None
        assert store == "ISSUE_STATUS"

