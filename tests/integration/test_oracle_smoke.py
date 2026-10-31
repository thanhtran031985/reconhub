from __future__ import annotations

import pytest
from sqlalchemy import Engine, text

from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.schemas.data_source import DataSourceCreateDTO
from app.services.data_source import create_data_source
from app.services.data_source import test_data_source as service_test_data_source


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


@pytest.mark.oracle
def test_service_test_data_source_oracle(oracle_test: Engine) -> None:
    """Kiểm tra hàm test_data_source của service qua kết nối Oracle thật."""
    settings = get_settings()
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])

    # Tạo data source dựa trên config test
    res = create_data_source(
        admin_ctx,
        DataSourceCreateDTO(
            name="ORACLE_TEST_INTEGRATION",
            env="DEV",
            purpose="SOURCE",
            db_type="ORACLE",
            host=settings.ORACLE_TEST_HOST,
            port=settings.ORACLE_TEST_PORT,
            service_name=settings.ORACLE_TEST_SERVICE,
            username=settings.ORACLE_TEST_USER,
            password=settings.ORACLE_TEST_PASSWORD,
            default_schema=settings.ORACLE_TEST_SRC_SCHEMA,
        ),
    )
    assert res.ok is True
    ds_id = res.data.id

    # Gọi kiểm tra kết nối
    test_res = service_test_data_source(admin_ctx, ds_id)
    assert test_res.ok is True
    assert test_res.data["ok"] is True


@pytest.mark.oracle
def test_validate_template_connected_oracle(oracle_test: Engine) -> None:
    """Kiểm tra xác thực template DTP với bảng Oracle thật qua VPN."""
    import json
    from pathlib import Path

    from app.schemas.template_config import TemplateConfig
    from app.services.template_validate import validate_template_connected

    settings = get_settings()
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])

    res = create_data_source(
        admin_ctx,
        DataSourceCreateDTO(
            name="ORACLE_TEST_TEMPLATE_VALIDATE",
            env="DEV",
            purpose="SOURCE",
            db_type="ORACLE",
            host=settings.ORACLE_TEST_HOST,
            port=settings.ORACLE_TEST_PORT,
            service_name=settings.ORACLE_TEST_SERVICE,
            username=settings.ORACLE_TEST_USER,
            password=settings.ORACLE_TEST_PASSWORD,
            default_schema=settings.ORACLE_TEST_SRC_SCHEMA,
        ),
    )
    assert res.ok is True
    ds_id = res.data.id

    sample_path = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
    with open(sample_path, "r", encoding="utf-8") as f:
        cfg = TemplateConfig.model_validate(json.load(f))

    val_res = validate_template_connected(admin_ctx, cfg, data_source_id=ds_id)
    assert val_res.ok is True
    assert val_res.data["is_valid"] is True
