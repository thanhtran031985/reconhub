"""Tests cho migration phân quyền — Bước 1 task 19 (test viết trước).

Kiểm tra: 4 bảng mới, RECON_USER_ROLE đổi sang ROLE_ID, seed vai trò +
menu tương đương v4, upgrade 2 lần, downgrade khi chỉ có vai trò seed,
downgrade khi có vai trò tự tạo thì báo lỗi rõ và không mất dữ liệu.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def _alembic_cfg(root: Path, db_url: str) -> Config:
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _upgrade(root: Path, db_url: str, revision: str = "head") -> None:
    command.upgrade(_alembic_cfg(root, db_url), revision)


def _downgrade(root: Path, db_url: str, revision: str = "base") -> None:
    command.downgrade(_alembic_cfg(root, db_url), revision)


@pytest.fixture
def root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def v4_db(tmp_path: Path, root: Path) -> str:
    """DB ở revision 0002 với 4 user v4 (mỗi user 1 vai trò cũ)."""
    db_path = tmp_path / "v4.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    _upgrade(root, db_url, "0002_add_lookup_tables")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        for i, (username, role) in enumerate(
            [
                ("admin", "ADMIN"),
                ("owner", "TEMPLATE_OWNER"),
                ("operator", "OPERATOR"),
                ("viewer", "VIEWER"),
            ],
            start=1,
        ):
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :f, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": i, "u": username, "f": username, "now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO RECON_USER_ROLE (USER_ID, ROLE, ORG_SCOPE, CREATED_AT) VALUES (:id, :role, NULL, :now)"
                ),
                {"id": i, "role": role, "now": now},
            )
    engine.dispose()
    return db_url


def test_upgrade_creates_tables_and_seeds(v4_db: str, root: Path) -> None:
    _upgrade(root, v4_db, "head")
    engine = create_engine(v4_db)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM RECON_MENU_GROUP")).scalar() == 3
        assert conn.execute(text("SELECT COUNT(*) FROM RECON_MENU")).scalar() == 13
        assert conn.execute(text("SELECT COUNT(*) FROM RECON_ROLE")).scalar() == 4
        admin = conn.execute(text("SELECT CODE, IS_SYSTEM FROM RECON_ROLE WHERE CODE='ADMIN'")).one()
        assert admin[1] == "Y"
        # ADMIN không có dòng ở RECON_ROLE_MENU
        assert conn.execute(text("SELECT COUNT(*) FROM RECON_ROLE_MENU")).scalar() == (8 + 6 + 5)
        # PERM_REVISION + MENU_SYNC_LOCK
        rev = conn.execute(text("SELECT VALUE FROM RECON_APP_SETTING WHERE KEY='PERM_REVISION'")).scalar()
        assert rev is not None and int(rev) >= 1
        lock = conn.execute(text("SELECT VALUE FROM RECON_APP_SETTING WHERE KEY='MENU_SYNC_LOCK'")).scalar()
        assert lock is not None
        # Mỗi user giữ đúng vai trò cũ qua ROLE_ID
        rows = conn.execute(
            text(
                "SELECT u.USERNAME, r.CODE FROM RECON_USER u "
                "JOIN RECON_USER_ROLE ur ON ur.USER_ID = u.ID "
                "JOIN RECON_ROLE r ON r.ID = ur.ROLE_ID ORDER BY u.USERNAME"
            )
        ).all()
        assert rows == [
            ("admin", "ADMIN"),
            ("operator", "OPERATOR"),
            ("owner", "TEMPLATE_OWNER"),
            ("viewer", "VIEWER"),
        ]
        # Không còn cột ROLE / ORG_SCOPE
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(RECON_USER_ROLE)"))]
        assert "ROLE" not in cols
        assert "ORG_SCOPE" not in cols
        assert "ROLE_ID" in cols
    engine.dispose()


def test_upgrade_idempotent(v4_db: str, root: Path) -> None:
    _upgrade(root, v4_db, "head")
    _upgrade(root, v4_db, "head")
    engine = create_engine(v4_db)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM RECON_ROLE")).scalar() == 4
        assert conn.execute(text("SELECT COUNT(*) FROM RECON_MENU")).scalar() == 13
    engine.dispose()


def test_downgrade_restores_old_roles(v4_db: str, root: Path) -> None:
    _upgrade(root, v4_db, "head")
    engine = create_engine(v4_db)
    with engine.connect() as conn:
        # Phải thật sự ở revision mới trước khi downgrade, nếu không test này
        # sẽ pass giả khi head vẫn là 0002.
        assert conn.execute(text("SELECT COUNT(*) FROM RECON_ROLE")).scalar() == 4
    engine.dispose()
    _downgrade(root, v4_db, "0002_add_lookup_tables")
    engine = create_engine(v4_db)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT USER_ID, ROLE FROM RECON_USER_ROLE ORDER BY USER_ID")).all()
        assert rows == [
            (1, "ADMIN"),
            (2, "TEMPLATE_OWNER"),
            (3, "OPERATOR"),
            (4, "VIEWER"),
        ]
        from sqlalchemy.exc import OperationalError

        with pytest.raises(OperationalError):
            conn.execute(text("SELECT 1 FROM RECON_ROLE LIMIT 1"))
    engine.dispose()


def test_downgrade_with_custom_role_fails_without_data_loss(v4_db: str, root: Path) -> None:
    _upgrade(root, v4_db, "head")
    engine = create_engine(v4_db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        role_id = conn.execute(
            text(
                "INSERT INTO RECON_ROLE (CODE, NAME, DESCRIPTION, IS_SYSTEM, IS_ACTIVE, "
                "CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES ('CUSTOM_X', 'Vai trò tự tạo', NULL, 'N', 'Y', 'admin', :now, 'admin', :now, 1)"
            ),
            {"now": now},
        ).lastrowid
        conn.execute(
            text(
                "INSERT INTO RECON_USER_ROLE (USER_ID, ROLE_ID, ASSIGNED_BY, ASSIGNED_AT, CREATED_AT) "
                "VALUES (2, :rid, 'admin', :now, :now)"
            ),
            {"rid": role_id, "now": now},
        )
    engine.dispose()
    with pytest.raises(Exception, match="CUSTOM_X"):
        _downgrade(root, v4_db, "0002_add_lookup_tables")
    # Dữ liệu vẫn còn nguyên sau lần downgrade lỗi
    engine = create_engine(v4_db)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM RECON_ROLE")).scalar() == 5
        assert (
            conn.execute(
                text("SELECT COUNT(*) FROM RECON_USER_ROLE WHERE ROLE_ID = :rid"),
                {"rid": role_id},
            ).scalar()
            == 1
        )
    engine.dispose()
