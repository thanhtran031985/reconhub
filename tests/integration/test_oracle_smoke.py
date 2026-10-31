from __future__ import annotations

import pytest
from sqlalchemy import Engine, text

from app.core.config import get_settings


@pytest.mark.oracle
def test_oracle_connection_and_smoke(oracle_test: Engine) -> None:
    """Kiểm tra kết nối và truy vấn thử 1 dòng từ bảng test trên Oracle."""
    settings = get_settings()
    with oracle_test.connect() as conn:
        res = conn.execute(text("SELECT 1 FROM DUAL")).scalar()
        assert res == 1

        # Nếu có schema nguồn test, thử đọc 1 dòng từ SRC_FACT_INVOICE_DTP
        schema = settings.ORACLE_TEST_SRC_SCHEMA
        table_name = f"{schema}.SRC_FACT_INVOICE_DTP" if schema else "SRC_FACT_INVOICE_DTP"
        try:
            row = conn.execute(text(f"SELECT * FROM {table_name} FETCH FIRST 1 ROWS ONLY")).fetchone()
            # Bảng có thể chưa có dòng nào hoặc có dữ liệu, nhưng câu query phải thành công
            assert row is None or len(row) > 0
        except Exception as exc:
            pytest.fail(f"Không thể truy vấn bảng test {table_name}: {exc}")
