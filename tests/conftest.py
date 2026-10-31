from __future__ import annotations

from typing import Generator

import pytest
from sqlalchemy import Engine, create_engine, text

from app.core.config import get_settings


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
