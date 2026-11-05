"""Tests cho Lookup service — Bước 1 (schema + seed) và Bước 2 (CRUD)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx, Role

# ─── Fixture DB ──────────────────────────────────────────────────────────────

@pytest.fixture()
def lookup_env(tmp_path, monkeypatch):
    """Tạo SQLite in-memory có đầy đủ schema cho test lookup."""
    db_path = tmp_path / "lookup_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    # Import metadata sau khi engine tạo xong để tránh circular import
    import app.services.lookup as lookup_mod
    from app.db.metadata import metadata

    metadata.create_all(engine)
    monkeypatch.setattr("app.db.engine.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: engine)
    # Luôn clear cache trước mỗi test để tránh nhiễu
    lookup_mod._lookup_cache.clear()

    yield engine

    lookup_mod._lookup_cache.clear()


def _admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])


def _viewer_ctx() -> Ctx:
    return Ctx(user_id=2, username="viewer", full_name="Viewer", roles=[Role.VIEWER])


# ─── Bước 1: seed / schema ───────────────────────────────────────────────────

class TestSeedData:
    def test_tables_exist(self, lookup_env):
        """Bảng RECON_LOOKUP_TYPE và RECON_LOOKUP_CODE phải tồn tại."""
        with lookup_env.connect() as conn:
            conn.execute(text("SELECT 1 FROM RECON_LOOKUP_TYPE LIMIT 1"))
            conn.execute(text("SELECT 1 FROM RECON_LOOKUP_CODE LIMIT 1"))

    def test_seed_creates_issue_status(self, lookup_env):
        """Seed tạo đủ 4 giá trị ISSUE_STATUS."""
        from app.services.lookup import ensure_default_lookup_data
        with lookup_env.begin() as conn:
            ensure_default_lookup_data(conn)
        with lookup_env.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM RECON_LOOKUP_CODE WHERE LOOKUP_TYPE='ISSUE_STATUS'")
            ).scalar()
        assert count == 4

    def test_seed_creates_issue_reason(self, lookup_env):
        """Seed tạo đủ các giá trị ISSUE_REASON."""
        from app.services.lookup import ensure_default_lookup_data
        with lookup_env.begin() as conn:
            ensure_default_lookup_data(conn)
        with lookup_env.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM RECON_LOOKUP_CODE WHERE LOOKUP_TYPE='ISSUE_REASON'")
            ).scalar()
        assert count >= 5

    def test_seed_idempotent(self, lookup_env):
        """Gọi seed 2 lần không tạo trùng dữ liệu."""
        from app.services.lookup import ensure_default_lookup_data
        with lookup_env.begin() as conn:
            ensure_default_lookup_data(conn)
        with lookup_env.begin() as conn:
            ensure_default_lookup_data(conn)
        with lookup_env.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM RECON_LOOKUP_TYPE")
            ).scalar()
        assert count == 2  # chỉ 2 type: ISSUE_STATUS, ISSUE_REASON


# ─── Bước 2: CRUD ────────────────────────────────────────────────────────────

class TestListLookupTypes:
    def test_list_returns_seeded_types(self, lookup_env):
        from app.services.lookup import ensure_default_lookup_data, list_lookup_types
        with lookup_env.begin() as conn:
            ensure_default_lookup_data(conn)
        res = list_lookup_types(_admin_ctx())
        assert res.ok
        codes = [t["lookup_type"] for t in res.data]
        assert "ISSUE_STATUS" in codes
        assert "ISSUE_REASON" in codes

    def test_viewer_can_list(self, lookup_env):
        from app.services.lookup import ensure_default_lookup_data, list_lookup_types
        with lookup_env.begin() as conn:
            ensure_default_lookup_data(conn)
        res = list_lookup_types(_viewer_ctx())
        assert res.ok


class TestCreateLookupType:
    def test_admin_can_create(self, lookup_env):
        from app.services.lookup import create_lookup_type
        res = create_lookup_type(_admin_ctx(), lookup_type="CURRENCY", type_name="Loại tiền tệ")
        assert res.ok

    def test_duplicate_lookup_type_fails(self, lookup_env):
        from app.services.lookup import create_lookup_type
        create_lookup_type(_admin_ctx(), lookup_type="CURRENCY", type_name="Loại tiền tệ")
        res = create_lookup_type(_admin_ctx(), lookup_type="CURRENCY", type_name="Loại tiền tệ 2")
        assert not res.ok

    def test_viewer_cannot_create(self, lookup_env):
        from app.services.lookup import create_lookup_type
        res = create_lookup_type(_viewer_ctx(), lookup_type="TEST", type_name="Test")
        assert not res.ok


class TestUpdateLookupType:
    def test_admin_can_update(self, lookup_env):
        from app.services.lookup import create_lookup_type, update_lookup_type
        create_lookup_type(_admin_ctx(), lookup_type="MYTYPE", type_name="My Type")
        res = update_lookup_type(_admin_ctx(), lookup_type="MYTYPE", type_name="My Type Updated")
        assert res.ok

    def test_viewer_cannot_update(self, lookup_env):
        from app.services.lookup import create_lookup_type, update_lookup_type
        create_lookup_type(_admin_ctx(), lookup_type="MYTYPE2", type_name="My Type 2")
        res = update_lookup_type(_viewer_ctx(), lookup_type="MYTYPE2", type_name="Changed")
        assert not res.ok


class TestListLookupCodes:
    def test_list_codes_for_type(self, lookup_env):
        from app.services.lookup import ensure_default_lookup_data, list_lookup_codes
        with lookup_env.begin() as conn:
            ensure_default_lookup_data(conn)
        res = list_lookup_codes(_admin_ctx(), lookup_type="ISSUE_STATUS")
        assert res.ok
        assert len(res.data) == 4

    def test_list_codes_unknown_type_returns_empty(self, lookup_env):
        from app.services.lookup import list_lookup_codes
        res = list_lookup_codes(_admin_ctx(), lookup_type="NONEXISTENT")
        assert res.ok
        assert res.data == []


class TestCreateLookupCode:
    def test_admin_can_create_code(self, lookup_env):
        from app.services.lookup import create_lookup_code, create_lookup_type
        create_lookup_type(_admin_ctx(), lookup_type="CURRENCY", type_name="Loại tiền tệ")
        res = create_lookup_code(
            _admin_ctx(),
            lookup_type="CURRENCY",
            lookup_code="VND",
            meaning="Đồng Việt Nam",
            display_order=1,
        )
        assert res.ok

    def test_duplicate_code_fails(self, lookup_env):
        from app.services.lookup import create_lookup_code, create_lookup_type
        create_lookup_type(_admin_ctx(), lookup_type="CURR2", type_name="Loại tiền")
        create_lookup_code(_admin_ctx(), lookup_type="CURR2", lookup_code="VND", meaning="VND", display_order=1)
        res = create_lookup_code(_admin_ctx(), lookup_type="CURR2", lookup_code="VND", meaning="VND dup", display_order=2)
        assert not res.ok

    def test_viewer_cannot_create_code(self, lookup_env):
        from app.services.lookup import create_lookup_code, create_lookup_type
        create_lookup_type(_admin_ctx(), lookup_type="CURR3", type_name="Loại tiền")
        res = create_lookup_code(_viewer_ctx(), lookup_type="CURR3", lookup_code="USD", meaning="Đô la", display_order=1)
        assert not res.ok


class TestUpdateLookupCode:
    def test_admin_can_update_code(self, lookup_env):
        from app.services.lookup import create_lookup_code, create_lookup_type, update_lookup_code
        create_lookup_type(_admin_ctx(), lookup_type="CURR4", type_name="Currency")
        create_lookup_code(_admin_ctx(), lookup_type="CURR4", lookup_code="EUR", meaning="Euro", display_order=1)
        res = update_lookup_code(
            _admin_ctx(),
            lookup_type="CURR4",
            lookup_code="EUR",
            meaning="Euro (EU)",
            display_order=2,
        )
        assert res.ok


class TestToggleLookupCodeStatus:
    def test_admin_can_toggle(self, lookup_env):
        from app.services.lookup import create_lookup_code, create_lookup_type, toggle_lookup_code_status
        create_lookup_type(_admin_ctx(), lookup_type="TGTYPE", type_name="Toggle")
        create_lookup_code(_admin_ctx(), lookup_type="TGTYPE", lookup_code="TG1", meaning="Toggle 1", display_order=1)
        res = toggle_lookup_code_status(_admin_ctx(), lookup_type="TGTYPE", lookup_code="TG1", is_active=False)
        assert res.ok

    def test_system_code_cannot_be_deleted(self, lookup_env):
        from app.services.lookup import delete_lookup_code, ensure_default_lookup_data
        with lookup_env.begin() as conn:
            ensure_default_lookup_data(conn)
        # OPEN là IS_SYSTEM='Y'
        res = delete_lookup_code(_admin_ctx(), lookup_type="ISSUE_STATUS", lookup_code="OPEN")
        assert not res.ok

    def test_viewer_cannot_toggle(self, lookup_env):
        from app.services.lookup import create_lookup_code, create_lookup_type, toggle_lookup_code_status
        create_lookup_type(_admin_ctx(), lookup_type="TGV", type_name="Toggle V")
        create_lookup_code(_admin_ctx(), lookup_type="TGV", lookup_code="X", meaning="X", display_order=1)
        res = toggle_lookup_code_status(_viewer_ctx(), lookup_type="TGV", lookup_code="X", is_active=False)
        assert not res.ok


class TestDeleteLookupCode:
    def test_admin_can_delete_non_system_code(self, lookup_env):
        from app.services.lookup import create_lookup_code, create_lookup_type, delete_lookup_code
        create_lookup_type(_admin_ctx(), lookup_type="DEL1", type_name="Delete test")
        create_lookup_code(_admin_ctx(), lookup_type="DEL1", lookup_code="X1", meaning="X1", display_order=1)
        res = delete_lookup_code(_admin_ctx(), lookup_type="DEL1", lookup_code="X1")
        assert res.ok

    def test_viewer_cannot_delete(self, lookup_env):
        from app.services.lookup import create_lookup_code, create_lookup_type, delete_lookup_code
        create_lookup_type(_admin_ctx(), lookup_type="DEL2", type_name="Delete test 2")
        create_lookup_code(_admin_ctx(), lookup_type="DEL2", lookup_code="Y1", meaning="Y1", display_order=1)
        res = delete_lookup_code(_viewer_ctx(), lookup_type="DEL2", lookup_code="Y1")
        assert not res.ok
