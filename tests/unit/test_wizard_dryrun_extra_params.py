from __future__ import annotations

from app.ui.pages.template_wizard import (
    _build_dry_extra_params_dict,
    _dry_extra_params,
    _dry_run_store,
    render_step_5,
)


def _config() -> dict:
    return {
        "template_code": "BILL_VTOS",
        "db_source": {
            "kind": "table",
            "table": "DATARAW.FACT_BILL",
            "filters": [
                {"param": "p_from", "column": "DATE_VALUE", "op": ">="},
                {"param": "p_to", "column": "DATE_VALUE", "op": "<="},
                {"param": "p_org", "column": "ORG_CODE", "op": "="},
                {"param": "p_application", "column": "APPLICATION", "op": "=", "skip_if_empty": True},
            ],
            "params": [
                {"name": "p_from", "type": "datetime", "required": True},
                {"name": "p_to", "type": "datetime", "required": True},
                {"name": "p_org", "type": "text", "default": "BDP", "required": True},
                {"name": "p_application", "type": "text", "default": "VTOS", "required": False},
            ],
        },
        "profiles": [{"code": "BY_INVOICE_VTOS", "is_default": True}],
    }


def test_dry_extra_params_exclude_fixed_and_keep_order() -> None:
    assert [p["name"] for p in _dry_extra_params(_config())] == ["p_application"]


def test_build_dry_extra_params_dict_skips_empty() -> None:
    assert _build_dry_extra_params_dict(_config(), ["VTOS"]) == {"p_application": "VTOS"}
    assert _build_dry_extra_params_dict(_config(), ["   "]) == {}
    assert _build_dry_extra_params_dict(_config(), [None]) == {}
    assert _build_dry_extra_params_dict(_config(), []) == {}


def test_render_step_5_shows_extra_param_with_default() -> None:
    ui = render_step_5(_config())
    text = str(ui)
    assert "p_application" in text
    assert "VTOS" in text


def test_render_step_5_prefers_value_from_last_dry_run() -> None:
    ui = render_step_5(_config(), dry_run_data={"extra_params": {"p_application": "XYZ"}})
    assert "XYZ" in str(ui)


def test_dry_run_store_keeps_extra_params() -> None:
    store = _dry_run_store(
        "done",
        None,
        "2026-11-03 00:00:00",
        "2026-11-03 23:59:59",
        "BDP",
        _config(),
        extra_params={"p_application": "VTOS"},
    )
    assert store["extra_params"] == {"p_application": "VTOS"}
    assert store["dry_run_ok"] is True
