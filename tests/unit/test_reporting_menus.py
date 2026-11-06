"""Tests cho seed menu reporting — Bước 3 task 21 (test viết trước).

sync_from_code thêm 3 menu mới (Q1/Q2); role seed gán đúng;
effective_menus trả đúng tập menu cho từng vai trò.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def menus_env(tmp_path, monkeypatch):
    db_path = tmp_path / "reporting_menus.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in ["app.services.menu_sync", "app.services.perm"]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [(1, "admin"), (2, "owner"), (3, "operator"), (4, "viewer")]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
    seed_perm_basics(
        engine,
        {1: ["ADMIN"], 2: ["TEMPLATE_OWNER"], 3: ["OPERATOR"], 4: ["VIEWER"]},
    )
    clear_perm_cache()
    return engine


class TestReportingMenusSeed:
    def test_sync_adds_three_menus(self, menus_env):
        from sqlalchemy import select

        from app.db.metadata import recon_menu

        with menus_env.connect() as conn:
            rows = {
                str(r["CODE"]): r
                for r in conn.execute(
                    select(recon_menu).where(
                        recon_menu.c.CODE.in_(["report_center", "report_history", "report_admin"])
                    )
                )
                .mappings()
                .all()
            }
        assert set(rows) == {"report_center", "report_history", "report_admin"}
        center = rows["report_center"]
        assert str(center["SOURCE_LABEL"]) == "Trung tâm báo cáo"
        assert str(center["SOURCE_GROUP"]) == "DOI_SOAT"
        assert str(center["PATH"]) == "/reports"
        assert int(center["SOURCE_ORDER"]) == 70
        assert str(center["IS_HIDEABLE"]) == "Y"
        assert str(center["IS_NEW"]) == "Y"
        history = rows["report_history"]
        assert str(history["SOURCE_GROUP"]) == "DOI_SOAT"
        assert str(history["PATH"]) == "/report-runs"
        assert int(history["SOURCE_ORDER"]) == 80
        admin = rows["report_admin"]
        assert str(admin["SOURCE_LABEL"]) == "Quản trị báo cáo"
        assert str(admin["SOURCE_GROUP"]) == "QUAN_TRI"
        assert str(admin["PATH"]) == "/report-admin"
        assert int(admin["SOURCE_ORDER"]) == 40
        assert str(admin["IS_HIDEABLE"]) == "N"

    def test_role_seed(self, menus_env):
        from app.ui.menus import ROLE_MENUS_SEED

        for role in ["TEMPLATE_OWNER", "OPERATOR", "VIEWER"]:
            assert "report_center" in ROLE_MENUS_SEED[role]
            assert "report_history" in ROLE_MENUS_SEED[role]
            assert "report_admin" not in ROLE_MENUS_SEED[role]
        assert "report_admin" not in ROLE_MENUS_SEED.get("ADMIN", [])

    def test_report_menus_skipped_from_sidebar(self, menus_env):
        """Task 27 chưa có trang: 3 menu report chưa hiện ở thanh bên
        (theo mẫu result/batch_run/batch_def)."""
        from app.ui.layout.shell import get_nav_items_for_menus

        items = get_nav_items_for_menus(
            {"dashboard", "report_center", "report_history", "report_admin"},
            engine=menus_env,
            is_admin=True,
        )
        hrefs = [item["href"] for group in items for item in group["items"]]
        assert "/reports" not in hrefs
        assert "/report-runs" not in hrefs
        assert "/report-admin" not in hrefs
        assert "/" in hrefs

    def test_effective_menus(self, menus_env):
        from app.services.perm import effective_menus

        engine = menus_env
        cases = [
            (1, "admin", ["ADMIN"], {"report_center", "report_history", "report_admin"}),
            (2, "owner", ["TEMPLATE_OWNER"], {"report_center", "report_history"}),
            (3, "operator", ["OPERATOR"], {"report_center", "report_history"}),
            (4, "viewer", ["VIEWER"], {"report_center", "report_history"}),
        ]
        for uid, username, roles, expected in cases:
            ctx = Ctx(user_id=uid, username=username, full_name=username, roles=roles)
            got = effective_menus(ctx, engine)
            assert expected <= got, f"{username}: thiếu {expected - got}"
            assert "report_admin" not in got or username == "admin"
