"""Test page Mô hình dữ liệu — bước 3: menu + route + skeleton + permission.

Viết trước (đỏ) rồi code cho xanh, theo quy tắc task.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx
from app.db.metadata import metadata, recon_user


@pytest.fixture
def dm_env(tmp_path, monkeypatch):
    db_file = tmp_path / "data_model_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res_adm = conn.execute(
            recon_user.insert().values(
                USERNAME="admin_test",
                FULL_NAME="Quản Trị Viên",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        adm_id = res_adm.inserted_primary_key[0]
        seed_perm_basics(engine, {adm_id: ["ADMIN"]}, conn=conn)

        res_op = conn.execute(
            recon_user.insert().values(
                USERNAME="op_test",
                FULL_NAME="Vận Hành Viên",
                PASSWORD_HASH=hash_password("op123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        op_id = res_op.inserted_primary_key[0]
        seed_perm_basics(engine, {op_id: ["OPERATOR"]}, conn=conn)

    return {
        "engine": engine,
        "admin_ctx": Ctx(user_id=adm_id, username="admin_test", full_name="Quản Trị Viên", roles=["ADMIN"]),
        "op_ctx": Ctx(user_id=op_id, username="op_test", full_name="Vận Hành Viên", roles=["OPERATOR"]),
    }


def _walk(node):
    """Duyệt cây component Dash theo chiều sâu."""
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


def test_menu_data_model_declared():
    """Menu data_model khai báo đúng nhóm QUẢN TRỊ, sau report_admin."""
    from app.ui.menus import MENU_BY_CODE, MENUS

    menu = MENU_BY_CODE["data_model"]
    assert menu.label == "Mô hình dữ liệu"
    assert menu.group == "QUAN_TRI"
    assert menu.path == "/data-model"
    assert menu.order == 50
    assert menu.icon == "lucide:network"
    assert menu.hideable == "Y"
    report_admin = MENU_BY_CODE["report_admin"]
    assert menu.order > report_admin.order
    assert menu in MENUS


def test_menu_visible_only_when_granted(dm_env):
    """ADMIN thấy menu; OPERATOR chưa cấp không thấy; cấp thì thấy."""
    from app.services.perm import clear_perm_cache, effective_menus

    assert "data_model" in effective_menus(dm_env["admin_ctx"], engine=dm_env["engine"])
    assert "data_model" not in effective_menus(dm_env["op_ctx"], engine=dm_env["engine"])

    # Cấp menu cho vai trò OPERATOR như ADMIN làm trên /roles.
    with dm_env["engine"].begin() as conn:
        role_id = conn.execute(text("SELECT ID FROM RECON_ROLE WHERE CODE = 'OPERATOR'")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO RECON_ROLE_MENU (ROLE_ID, MENU_CODE, GRANTED_BY, GRANTED_AT) "
                "VALUES (:rid, 'data_model', 'admin_test', :now)"
            ),
            {"rid": int(role_id), "now": datetime.now(timezone.utc).replace(tzinfo=None)},
        )
    clear_perm_cache()
    assert "data_model" in effective_menus(dm_env["op_ctx"], engine=dm_env["engine"])


def test_get_data_model_returns_manifest_and_drift(dm_env):
    """Service trả 43 bảng từ manifest đã commit + drift SYNCED trên DB test."""
    from app.services.data_model import get_data_model

    res = get_data_model(dm_env["admin_ctx"])
    assert res.ok, res.message
    assert res.data is not None
    tables = res.data["manifest"]["tables"]
    assert len(tables) == 43
    names = {t["name"] for t in tables}
    assert "RECON_RUN" in names
    assert "RECON_RPT_PARAM" in names
    assert res.data["drift"]["status"] == "SYNCED"
    assert res.data["drift"]["drifts"] == []
    assert isinstance(res.data["history"], list)
    assert len(res.data["history"]) == 58


def test_get_data_model_forbidden_without_menu(dm_env):
    """Service bị chặn khi vai trò chưa được cấp menu data_model."""
    from app.services.data_model import get_data_model

    res = get_data_model(dm_env["op_ctx"])
    assert not res.ok
    assert res.code is not None
    assert "data_model" in str(res.details or "") or "quyền" in res.message.lower()


def test_layout_gate_redirects(dm_env, monkeypatch):
    """Chưa đăng nhập -> /login; không quyền -> /forbidden."""
    import app.ui.pages.data_model as page

    monkeypatch.setattr(page, "get_current_ctx", lambda: None)
    node = page.layout()
    assert "/login" in str(node)

    monkeypatch.setattr(page, "get_current_ctx", lambda: dm_env["op_ctx"])
    node = page.layout()
    assert "/forbidden" in str(node)


def test_layout_admin_skeleton(dm_env, monkeypatch):
    """ADMIN vào được: Box cao calc(100vh - 88px), đủ 3 panel + stores."""
    import app.ui.pages.data_model as page

    monkeypatch.setattr(page, "get_current_ctx", lambda: dm_env["admin_ctx"])
    box = page.layout()
    assert box.style["height"] == "calc(100vh - 88px)"
    text = str(box)
    assert "Mô hình dữ liệu" in text
    assert "Lịch sử thay đổi" in text
    assert "Đồng bộ schema" in text
    assert "data-model-search" in text
    for store_id in (
        "data-model-manifest-store",
        "data-model-selection-store",
        "data-model-ui-store",
        "data-model-dblclick-store",
    ):
        assert store_id in text, store_id
    nodes = list(_walk(box))
    ids = {getattr(n, "id", None) for n in nodes}
    assert "data-model-explorer-container" in ids
    assert "data-model-canvas-container" in ids
    assert "data-model-detail-container" in ids
    assert "data-model-status-bar" in ids


def test_layout_accepts_query_kwargs(dm_env, monkeypatch):
    """layout(**kwargs) đọc ?table=... và preselect table đó."""
    import app.ui.pages.data_model as page

    monkeypatch.setattr(page, "get_current_ctx", lambda: dm_env["admin_ctx"])
    box = page.layout(table="RECON_RUN")
    nodes = list(_walk(box))
    store = next(n for n in nodes if getattr(n, "id", None) == "data-model-selection-store")
    assert store.data["kind"] == "table"
    assert store.data["table"] == "RECON_RUN"
    box2 = page.layout(table="RECON_RUN", domain="recon", mode="compact")
    store2 = next(n for n in _walk(box2) if getattr(n, "id", None) == "data-model-selection-store")
    assert store2.data["table"] == "RECON_RUN"
