from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.core.context import Ctx, Role
from app.schemas.errors import ErrorCode
from app.schemas.template_config import TemplateConfig
from app.services.template_validate import validate_template_connected

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_sample_config() -> TemplateConfig:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TemplateConfig.model_validate(data)


@pytest.fixture
def auth_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])


@pytest.fixture
def mock_catalog_dtp() -> dict[str, Any]:
    tables = [
        {"name": "SRC_FACT_INVOICE_DTP", "type": "TABLE", "schema": "RECON_SRC"}
    ]
    columns = [
        {"name": "COLLECT_POINT", "data_type": "VARCHAR2", "nullable": True, "length": 50, "precision": None, "scale": None},
        {"name": "TXN_ID", "data_type": "VARCHAR2", "nullable": True, "length": 100, "precision": None, "scale": None},
        {"name": "INVOICE_NO", "data_type": "VARCHAR2", "nullable": False, "length": 50, "precision": None, "scale": None},
        {"name": "INVOICE_STATUS", "data_type": "VARCHAR2", "nullable": True, "length": 20, "precision": None, "scale": None},
        {"name": "INVOICE_DATE", "data_type": "TIMESTAMP", "nullable": False, "length": None, "precision": None, "scale": None},
        {"name": "PIN_NO", "data_type": "VARCHAR2", "nullable": True, "length": 50, "precision": None, "scale": None},
        {"name": "SERVICE_CODE", "data_type": "VARCHAR2", "nullable": True, "length": 50, "precision": None, "scale": None},
        {"name": "QUANTITY", "data_type": "NUMBER", "nullable": True, "length": None, "precision": 10, "scale": 0},
        {"name": "AMOUNT", "data_type": "NUMBER", "nullable": True, "length": None, "precision": 18, "scale": 2},
        {"name": "ORG_CODE", "data_type": "VARCHAR2", "nullable": True, "length": 20, "precision": None, "scale": None},
    ]
    return {"tables": tables, "columns": columns}


def test_validate_template_connected_success(auth_ctx, mock_catalog_dtp) -> None:
    cfg = get_sample_config()

    with patch("app.services.template_validate.list_tables") as mock_tables, \
         patch("app.services.template_validate.list_columns") as mock_cols:
        mock_tables.return_value = mock_catalog_dtp["tables"]
        mock_cols.return_value = mock_catalog_dtp["columns"]

        res = validate_template_connected(auth_ctx, cfg, data_source_id=1)
        assert res.ok is True
        assert res.data is not None
        assert res.data["is_valid"] is True
        assert len(res.data["errors"]) == 0


def test_validate_template_connected_table_not_found(auth_ctx) -> None:
    cfg = get_sample_config()

    with patch("app.services.template_validate.list_tables") as mock_tables:
        mock_tables.return_value = []  # Không có bảng nào

        res = validate_template_connected(auth_ctx, cfg, data_source_id=1)
        assert res.ok is True
        assert res.data["is_valid"] is False
        assert any(e["code"] == ErrorCode.TABLE_NOT_FOUND and e["path"] == "db_source.table" for e in res.data["errors"])


def test_validate_template_connected_column_not_found(auth_ctx, mock_catalog_dtp) -> None:
    cfg = get_sample_config()

    # Bỏ cột AMOUNT khỏi bảng DB
    cols_without_amount = [c for c in mock_catalog_dtp["columns"] if c["name"] != "AMOUNT"]

    with patch("app.services.template_validate.list_tables") as mock_tables, \
         patch("app.services.template_validate.list_columns") as mock_cols:
        mock_tables.return_value = mock_catalog_dtp["tables"]
        mock_cols.return_value = cols_without_amount

        res = validate_template_connected(auth_ctx, cfg, data_source_id=1)
        assert res.ok is True
        assert res.data["is_valid"] is False
        # Cột AMOUNT ở fields[9].db
        assert any(e["code"] == ErrorCode.COLUMN_NOT_FOUND and "fields" in e["path"] and ".db" in e["path"] for e in res.data["errors"])


def test_validate_template_connected_time_filter_not_date_type(auth_ctx, mock_catalog_dtp) -> None:
    cfg = get_sample_config()

    # Đổi kiểu INVOICE_DATE thành VARCHAR2
    cols_varchar_date = []
    for c in mock_catalog_dtp["columns"]:
        c_copy = dict(c)
        if c_copy["name"] == "INVOICE_DATE":
            c_copy["data_type"] = "VARCHAR2"
        cols_varchar_date.append(c_copy)

    with patch("app.services.template_validate.list_tables") as mock_tables, \
         patch("app.services.template_validate.list_columns") as mock_cols:
        mock_tables.return_value = mock_catalog_dtp["tables"]
        mock_cols.return_value = cols_varchar_date

        res = validate_template_connected(auth_ctx, cfg, data_source_id=1)
        assert res.ok is True
        assert res.data["is_valid"] is False
        assert any("filters" in e["path"] and "DATE" in e["message"] for e in res.data["errors"])


def test_validate_template_connected_warns_on_connection_failure(auth_ctx) -> None:
    cfg = get_sample_config()

    with patch("app.services.template_validate.list_tables") as mock_tables:
        mock_tables.side_effect = RuntimeError("Oracle connection lost")

        res = validate_template_connected(auth_ctx, cfg, data_source_id=1)
        # Không chặn, vẫn trả ok=True nhưng có warning
        assert res.ok is True
        assert res.data["is_valid"] is True
        assert len(res.data["warnings"]) > 0
        assert "Không thể kết nối" in res.data["warnings"][0]


def test_validate_template_connected_no_data_source(auth_ctx) -> None:
    cfg = get_sample_config()
    res = validate_template_connected(auth_ctx, cfg, data_source_id=None)
    assert res.ok is True
    assert res.data["is_valid"] is True
    assert len(res.data["warnings"]) > 0
