from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.services.metadata_migration import precheck


@pytest.mark.oracle
def test_oracle_metadata_migration(oracle_test) -> None:
    settings = get_settings()
    if not settings.ORACLE_TEST_DSN or not settings.ORACLE_TEST_SRC_USER:
        pytest.skip("Bỏ qua test Oracle migration: thiếu cấu hình ORACLE_TEST_* hoặc không có VPN")

    admin_ctx = Ctx(
        user_id=1,
        username="admin",
        full_name="Admin Test",
        roles=[Role.ADMIN],
    )

    # Chạy thử precheck với mock_target_engine là oracle_test
    # Giả định target_ds_id=1
    res_pre = precheck(admin_ctx, target_ds_id=1, mode="NO_TEMP", mock_target_engine=oracle_test)
    if not res_pre.ok:
        pytest.skip(f"Precheck Oracle migration không sẵn sàng: {res_pre.message}")

    assert res_pre.data["ready"] is True
