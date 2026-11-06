from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator

import pytest
from sqlalchemy import Engine, create_engine, text

from app.core.config import get_settings


def _seed_perm_rows(conn, assignments, now, role_ids: dict[str, int]) -> None:
    """Chèn vai trò/menu/gán vai trò trên một connection sẵn có."""
    from app.ui.menus import ROLE_MENUS_SEED

    for code, is_system in [
        ("ADMIN", "Y"),
        ("TEMPLATE_OWNER", "N"),
        ("OPERATOR", "N"),
        ("VIEWER", "N"),
    ]:
        existing = conn.execute(
            text("SELECT ID FROM RECON_ROLE WHERE CODE = :code"), {"code": code}
        ).scalar_one_or_none()
        if existing is not None:
            role_ids[code] = int(existing)
            continue
        res = conn.execute(
            text(
                "INSERT INTO RECON_ROLE (CODE, NAME, IS_SYSTEM, IS_ACTIVE, "
                "CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES (:code, :code, :sys, 'Y', 'SEED', :now, 'SEED', :now, 1)"
            ),
            {"code": code, "sys": is_system, "now": now},
        )
        role_ids[code] = int(res.lastrowid)
    for role_code, menus in ROLE_MENUS_SEED.items():
        for menu in menus:
            granted = conn.execute(
                text("SELECT 1 FROM RECON_ROLE_MENU WHERE ROLE_ID = :rid AND MENU_CODE = :menu"),
                {"rid": role_ids[role_code], "menu": menu},
            ).scalar_one_or_none()
            if granted is None:
                conn.execute(
                    text(
                        "INSERT INTO RECON_ROLE_MENU (ROLE_ID, MENU_CODE, GRANTED_BY, GRANTED_AT) "
                        "VALUES (:rid, :menu, 'SEED', :now)"
                    ),
                    {"rid": role_ids[role_code], "menu": menu, "now": now},
                )
    for user_id, roles in (assignments or {}).items():
        for role_code in roles:
            assigned = conn.execute(
                text("SELECT 1 FROM RECON_USER_ROLE WHERE USER_ID = :uid AND ROLE_ID = :rid"),
                {"uid": user_id, "rid": role_ids[role_code]},
            ).scalar_one_or_none()
            if assigned is None:
                conn.execute(
                    text(
                        "INSERT INTO RECON_USER_ROLE (USER_ID, ROLE_ID, ASSIGNED_BY, ASSIGNED_AT, CREATED_AT) "
                        "VALUES (:uid, :rid, 'SEED', :now, :now)"
                    ),
                    {"uid": user_id, "rid": role_ids[role_code], "now": now},
                )


def seed_perm_basics(
    engine: Engine,
    assignments: dict[int, list[str]] | None = None,
    conn: object = None,
) -> dict[str, int]:
    """Seed dữ liệu phân quyền tối thiểu cho fixture test cũ (task 19).

    Đồng bộ menu từ code, tạo 4 vai trò seed kèm menu, rồi gán vai trò cho
    các user đã tồn tại trong DB theo `assignments` ({user_id: [mã vai trò]}).
    Trả về {mã vai trò: role_id}. Xóa cache quyền sau khi seed để test sau
    không dùng nhầm cache của DB khác. Truyền `conn` khi gọi trong một
    transaction đang mở để thấy các user vừa chèn chưa commit; khi đó
    menu/vai trò phải được đồng bộ trước bằng một lần gọi không có `conn`
    (đồng bộ mở transaction riêng nên không gọi được trong transaction).
    """
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    role_ids: dict[str, int] = {}
    if conn is not None:
        _seed_perm_rows(conn, assignments, now, role_ids)
    else:
        sync_from_code(engine)
        with engine.begin() as conn:
            _seed_perm_rows(conn, assignments, now, role_ids)
    clear_perm_cache()
    return role_ids


@pytest.fixture(autouse=True)
def _clear_perm_cache() -> Generator[None, None, None]:
    """Xóa cache quyền trước/sau mỗi test (task 19).

    Cache menu hiệu lực key theo (user_id, PERM_REVISION); các test dùng
    DB tạm khác nhau nhưng cùng user_id/revision nên cache cũ sẽ rò
    sang test sau nếu không xóa.
    """
    from app.services.perm import clear_perm_cache

    clear_perm_cache()
    yield
    clear_perm_cache()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Generator[None, None, None]:
    """Xóa cache settings trước/sau mỗi test (task 20 bước 3).

    `get_settings` là lru_cache: fixture đổi RECON_DB_URL (kèm
    cache_clear ở setup, không có ở teardown) sẽ để settings trỏ sang
    DB tạm của test trước, khiến test sau dùng nhầm engine — ví dụ
    test_page_dashboard để user_id=1 là operator, làm thanh bên của
    test_ui_shell rỗng vì `get_nav_items_for_menus` giờ đọc cây menu
    từ DB thay vì hằng số code.
    """
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def oracle_test() -> Generator[Engine, None, None]:
    """Fixture kết nối tới CSDL Oracle test qua VPN.

    Tự động skip nếu thiếu các biến môi trường ORACLE_TEST_*
    hoặc không kết nối được qua VPN.
    """
    settings = get_settings()
    if not settings.ORACLE_TEST_DSN or not settings.ORACLE_TEST_SRC_USER or not settings.ORACLE_TEST_SRC_PASSWORD:
        pytest.skip("Thiếu cấu hình ORACLE_TEST_* trong môi trường; tự động skip test Oracle.")

    # Tạo URL kết nối Oracle Thin mode
    oracle_url = (
        f"oracle+oracledb://{settings.ORACLE_TEST_SRC_USER}:{settings.ORACLE_TEST_SRC_PASSWORD}@"
        f"{settings.ORACLE_TEST_DSN}"
    )

    try:
        engine = create_engine(oracle_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM DUAL"))
    except Exception as exc:
        pytest.skip(f"Không thể kết nối tới Oracle server qua VPN: {exc}")

    yield engine
    engine.dispose()
