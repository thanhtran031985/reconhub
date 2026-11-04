from __future__ import annotations

from app.ui.pages.template_wizard import (
    _extra_filters_from_db_spec,
    _render_profile_grouped_sql,
    _sync_db_source_filters_and_params,
    render_step_3,
)


def _saved_db_spec() -> dict:
    """Bản đã lưu trong DB: có filters/params đầy đủ nhưng rớt extra_filters
    vì TemplateConfig validate với DbSourceSpec extra='ignore'."""
    return {
        "kind": "table",
        "table": "DATARAW.FACT_BILL",
        "source_id": "GMD_DEV",
        "pushdown_aggregate": True,
        "filters": [
            {"param": "p_from", "column": "DATE_VALUE", "op": ">=", "cast": "none"},
            {"param": "p_to", "column": "DATE_VALUE", "op": "<=", "cast": "none"},
            {"param": "p_org", "column": "ORG_CODE", "op": "=", "cast": "none"},
            {"param": "p_application", "column": "APPLICATION", "op": "=", "cast": "none", "skip_if_empty": True},
        ],
        "params": [
            {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
            {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
            {
                "name": "p_org",
                "type": "text",
                "source": "default",
                "default": "BDP",
                "label": "Đơn vị",
                "required": True,
            },
            {
                "name": "p_application",
                "type": "text",
                "source": "user",
                "default": "VTOS",
                "label": "Tham Số 1",
                "required": False,
            },
        ],
        "_columns": [
            ("INVOICE_NO", "VARCHAR2"),
            ("INVOICE_DATE", "DATE"),
            ("TOTAL_AMOUNT", "NUMBER"),
            ("DATE_VALUE", "DATE"),
            ("ORG_CODE", "VARCHAR2"),
            ("APPLICATION", "VARCHAR2"),
        ],
    }


def _saved_config() -> dict:
    return {
        "template_code": "BILL_VTOS",
        "name": "Hóa đơn Vtos",
        "fields": [
            {"name": "SO_HD", "label": "Số HD", "type": "text", "excel": "Số hóa đơn", "db": "INVOICE_NO"},
            {
                "name": "NGAY_HD",
                "label": "Ngày HD",
                "type": "datetime",
                "excel": "Ngày lập hóa đơn",
                "db": "INVOICE_DATE",
            },
            {"name": "AMOUNT", "label": "Tổng tiền", "type": "number", "excel": "Thành tiền", "db": "TOTAL_AMOUNT"},
        ],
        "db_source": _saved_db_spec(),
        "profiles": [
            {
                "code": "BY_INVOICE_VTOS",
                "name": "Bill Vtos",
                "is_default": True,
                "group_by": ["SO_HD"],
                "measures": [{"name": "TOTAL_TONG_TIEN", "agg": "sum", "field": "AMOUNT"}],
            }
        ],
    }


def test_extra_filters_recovered_from_saved_filters_params() -> None:
    extras = _extra_filters_from_db_spec(_saved_db_spec())
    assert [e["param"] for e in extras] == ["p_application"]
    assert extras[0]["column"] == "APPLICATION"
    assert extras[0]["default"] == "VTOS"


def test_extra_filters_not_resurrected_when_key_present_but_empty() -> None:
    # Người dùng đã xóa hết tham số phụ: key có nhưng rỗng thì không được
    # khôi phục lại từ filters/params cũ.
    spec = _saved_db_spec()
    spec["extra_filters"] = []
    assert _extra_filters_from_db_spec(spec) == []


def test_sync_preserves_saved_extra_param_when_key_absent() -> None:
    cfg = {"db_source": _saved_db_spec()}
    assert "extra_filters" not in cfg["db_source"]
    _sync_db_source_filters_and_params(cfg)
    assert [f["param"] for f in cfg["db_source"]["filters"]] == ["p_from", "p_to", "p_org", "p_application"]
    assert [p["name"] for p in cfg["db_source"]["params"]] == ["p_from", "p_to", "p_org", "p_application"]
    assert [e["param"] for e in cfg["db_source"]["extra_filters"]] == ["p_application"]


def test_render_step_3_shows_saved_extra_param_without_extra_filters_key() -> None:
    ui = render_step_3(_saved_config())
    text = str(ui)
    assert "p_application" in text
    assert "APPLICATION" in text
    assert ":p_application" in text


def test_step4_placeholder_lists_extra_binds_not_only_three_fixed() -> None:
    sql = _render_profile_grouped_sql(
        _saved_config(),
        ["SO_HD"],
        [{"name": "TOTAL_TONG_TIEN", "agg": "sum", "field": "AMOUNT"}],
    )
    assert ":p_application" in sql
    assert ":p_from, :p_to, :p_org, :p_application" in sql


def test_step4_placeholder_unchanged_when_no_extra_params() -> None:
    cfg = _saved_config()
    cfg["db_source"]["filters"] = cfg["db_source"]["filters"][:3]
    cfg["db_source"]["params"] = cfg["db_source"]["params"][:3]
    sql = _render_profile_grouped_sql(
        cfg,
        ["SO_HD"],
        [{"name": "TOTAL_TONG_TIEN", "agg": "sum", "field": "AMOUNT"}],
    )
    assert ":p_from, :p_to, :p_org>" in sql
    assert ":p_application" not in sql
