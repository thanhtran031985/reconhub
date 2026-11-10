"""Task 41: padding 5 trang giống /report-admin; /account padding + canh giữa.

Tham chiếu: #admin-list-container của /report-admin có padding "8px 12px".
5 trang /data-sources, /lookups, /users, /roles, /menus trước đây root
không có padding nên nội dung dính sát mép khung. /account root không
padding và cột maw=640 lệch trái (thiếu mx="auto").
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine

from app.core.context import Ctx
from app.db.metadata import metadata, recon_user

PAD = "8px 12px"


@pytest.fixture
def padding_env(monkeypatch, tmp_path):
    """DB tạm + admin + phân quyền task 19 cho 6 layout."""
    from tests.conftest import seed_perm_basics

    db_path = tmp_path / "padding41.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    engine = create_engine(db_url)
    metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                ID=1,
                USERNAME="admin",
                FULL_NAME="Quản trị viên",
                PASSWORD_HASH="hash",
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
    seed_perm_basics(engine, {1: ["ADMIN"]})
    for mod in [
        "app.services.perm",
        "app.services.data_source",
        "app.services.temp_data",
        "app.services.user",
        "app.services.role",
        "app.services.menu_admin",
        "app.services.lookup",
        "app.db.engine",
        "app.ui.pages.data_sources",
        "app.ui.pages.lookups",
        "app.ui.pages.users",
        "app.ui.pages.roles",
        "app.ui.pages.menus",
        "app.ui.pages.account",
        "app.ui.pages.report_admin",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine, raising=False)
    return engine


def _admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Quản trị viên", roles=["ADMIN"])


def _root_style(page: Any) -> dict:
    assert isinstance(page.style, dict), f"root không có style dict: {type(page)}"
    return page.style


def _walk(comp: Any):
    yield comp
    children = getattr(comp, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


class TestReportAdminReference:
    def test_report_admin_list_padding_is_8px_12px(self, padding_env, monkeypatch) -> None:
        """Khóa giá trị tham chiếu: list /report-admin padding 8px 12px."""
        from app.ui.pages.report_admin import layout

        monkeypatch.setattr("app.ui.pages.report_admin.get_current_ctx", lambda: _admin_ctx())
        page = layout()
        container = next(
            c for c in _walk(page) if getattr(c, "id", None) == "admin-list-container"
        )
        assert container.style.get("padding") == PAD


class TestFivePagesPadding:
    @pytest.mark.parametrize(
        "module",
        [
            "data_sources",
            "lookups",
            "users",
            "roles",
            "menus",
        ],
    )
    def test_root_padding_matches_report_admin(self, padding_env, monkeypatch, module) -> None:
        import importlib

        page_mod = importlib.import_module(f"app.ui.pages.{module}")
        monkeypatch.setattr(f"app.ui.pages.{module}.get_current_ctx", lambda: _admin_ctx())
        page = page_mod.layout()
        assert _root_style(page).get("padding") == PAD, module


class TestAccountPadding:
    def test_account_root_padding_and_content_centered(self, padding_env, monkeypatch) -> None:
        from app.ui.pages.account import layout

        monkeypatch.setattr("app.ui.pages.account.get_current_ctx", lambda: _admin_ctx())
        page = layout()
        assert _root_style(page).get("padding") == PAD
        stacks = [
            c
            for c in _walk(page)
            if c.__class__.__name__ == "Stack" and getattr(c, "maw", None) == 640
        ]
        assert len(stacks) == 1, f"tìm thấy {len(stacks)} Stack maw=640"
        assert stacks[0].mx == "auto"
