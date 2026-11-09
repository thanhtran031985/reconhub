"""Tests cho khai báo menu và đồng bộ — Bước 2 task 19 (test viết trước)."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.db.metadata import metadata


@pytest.fixture()
def sync_env(tmp_path, monkeypatch):
    db_path = tmp_path / "menu_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    monkeypatch.setattr("app.db.engine.get_recon_engine", lambda: engine)
    import app.services.menu_sync as sync_mod

    monkeypatch.setattr("app.services.menu_sync.get_recon_engine", lambda: engine)
    yield engine, sync_mod, str(db_path)
    engine.dispose()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sync_in_process(db_path: str) -> dict:
    from sqlalchemy import create_engine

    from app.services.menu_sync import sync_from_code

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        return sync_from_code(engine)
    finally:
        engine.dispose()


class TestMenuDeclaration:
    def test_menus_match_migration_seed(self):
        # So sánh trực tiếp với hằng seed trong revision 0003
        import importlib.util

        from app.ui.menus import GROUPS, MENUS

        root = Path(__file__).resolve().parent.parent.parent
        spec = importlib.util.spec_from_file_location(
            "mig0003", root / "migrations" / "versions" / "0003_menu_permission.py"
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert [(g.code, g.label, g.order) for g in GROUPS] == list(mod.SEED_GROUPS)
        # Seed 0003 là lịch sử đóng băng; menu thêm sau (task 21) không có trong đó.
        menus = [(m.code, m.label, m.group, m.path, m.order, m.icon, m.hideable) for m in MENUS]
        assert all(s in menus for s in mod.SEED_MENUS)
        assert len(MENUS) == 17  # 13 menu gốc + 3 menu report (task 21) + 1 menu data model (task 31)
        assert len(GROUPS) == 3

    def test_menu_codes_unique_and_valid(self):
        import re

        from app.ui.menus import GROUPS, MENUS

        assert len({m.code for m in MENUS}) == len(MENUS)
        for m in MENUS:
            assert re.match(r"^[a-z][a-z0-9_]{1,39}$", m.code), m.code
        for g in GROUPS:
            assert re.match(r"^[A-Z][A-Z0-9_]{1,39}$", g.code), g.code


class TestMenuSync:
    def test_sync_adds_menus_and_groups(self, sync_env):
        engine, sync_mod, _ = sync_env
        res = sync_mod.sync_from_code(engine)
        assert res["added_menus"] == 17
        assert res["added_groups"] == 3
        assert res["changed"] is True
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM RECON_MENU")).scalar() == 17
            assert conn.execute(text("SELECT COUNT(*) FROM RECON_MENU_GROUP")).scalar() == 3
            assert conn.execute(text("SELECT COUNT(*) FROM RECON_MENU WHERE IS_NEW='Y'")).scalar() == 17
            assert conn.execute(text("SELECT VALUE FROM RECON_APP_SETTING WHERE KEY='PERM_REVISION'")).scalar() == "1"
            # Không thêm menu vào vai trò nào
            assert conn.execute(text("SELECT COUNT(*) FROM RECON_ROLE_MENU")).scalar() == 0

    def test_sync_idempotent_no_revision_bump(self, sync_env):
        engine, sync_mod, _ = sync_env
        sync_mod.sync_from_code(engine)
        res = sync_mod.sync_from_code(engine)
        assert res["changed"] is False
        assert res["added"] == 0
        with engine.connect() as conn:
            assert conn.execute(text("SELECT VALUE FROM RECON_APP_SETTING WHERE KEY='PERM_REVISION'")).scalar() == "1"

    def test_sync_updates_source_not_display(self, sync_env, monkeypatch):
        engine, sync_mod, _ = sync_env
        sync_mod.sync_from_code(engine)
        # Admin chỉnh tên hiển thị
        with engine.begin() as conn:
            conn.execute(text("UPDATE RECON_MENU SET DISPLAY_LABEL='Tên riêng' WHERE CODE='dashboard'"))
        # Code đổi label gốc
        from app.ui import menus as menus_mod

        changed = [
            m
            if m.code != "dashboard"
            else menus_mod.MenuDef(
                code=m.code,
                label="Bảng điều khiển",
                group=m.group,
                path=m.path,
                order=m.order,
                icon=m.icon,
                hideable=m.hideable,
            )
            for m in menus_mod.MENUS
        ]
        monkeypatch.setattr(menus_mod, "MENUS", changed)
        res = sync_mod.sync_from_code(engine)
        assert res["changed"] is True
        with engine.connect() as conn:
            row = conn.execute(text("SELECT SOURCE_LABEL, DISPLAY_LABEL FROM RECON_MENU WHERE CODE='dashboard'")).one()
            assert row[0] == "Bảng điều khiển"
            assert row[1] == "Tên riêng"

    def test_sync_removes_and_restores_menu(self, sync_env, monkeypatch):
        engine, sync_mod, _ = sync_env
        sync_mod.sync_from_code(engine)
        from app.ui import menus as menus_mod

        original = list(menus_mod.MENUS)
        # Bỏ menu khỏi code
        monkeypatch.setattr(menus_mod, "MENUS", [m for m in original if m.code != "lookup"])
        sync_mod.sync_from_code(engine)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT IS_REMOVED FROM RECON_MENU WHERE CODE='lookup'")).scalar() == "Y"
        # Xuất hiện lại
        monkeypatch.setattr(menus_mod, "MENUS", original)
        res = sync_mod.sync_from_code(engine)
        assert res["changed"] is True
        with engine.connect() as conn:
            assert conn.execute(text("SELECT IS_REMOVED FROM RECON_MENU WHERE CODE='lookup'")).scalar() == "N"

    def test_two_processes_sync_concurrently(self, sync_env):
        _, _, db_path = sync_env
        with ProcessPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(_sync_in_process, [db_path, db_path]))
        # Một process đồng bộ đủ 17 menu, process kia bỏ qua vì khóa đang giữ
        assert sum(r.get("added_menus", 0) for r in results) == 17
        assert all(r.get("added_menus", 0) in (0, 17) for r in results)
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM RECON_MENU")).scalar() == 17
            assert conn.execute(text("SELECT COUNT(*) FROM RECON_MENU_GROUP")).scalar() == 3
            assert conn.execute(text("SELECT COUNT(*) FROM RECON_ROLE_MENU")).scalar() == 0
        engine.dispose()
