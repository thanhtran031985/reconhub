from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.template_config import TemplateConfig

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def load_sample_config() -> dict[str, Any]:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def test_sample_dtp_template_is_valid() -> None:
    data = load_sample_config()
    cfg = TemplateConfig.model_validate(data)
    assert cfg.schema_version == 1
    assert cfg.file.sheet == "BÁO CÁO DTP"
    assert len(cfg.fields) == 10
    assert len(cfg.derived) == 1
    assert cfg.db_source.kind == "table"
    assert len(cfg.profiles) == 3


def test_file_header_row_invalid() -> None:
    data = load_sample_config()
    data["file"]["header_row"] = 0
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("header_row" in str(err["loc"]) for err in exc.value.errors())


def test_file_data_start_row_must_be_greater_than_header() -> None:
    data = load_sample_config()
    data["file"]["header_row"] = 5
    data["file"]["data_start_row"] = 5
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("data_start_row" in str(err["loc"]) for err in exc.value.errors())


def test_file_skip_footer_rows_negative() -> None:
    data = load_sample_config()
    data["file"]["skip_footer_rows"] = -1
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("skip_footer_rows" in str(err["loc"]) for err in exc.value.errors())


def test_field_name_invalid_regex() -> None:
    data = load_sample_config()
    data["fields"][0]["name"] = "123_INVALID"
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    err = exc.value.errors()[0]
    assert "fields" in err["loc"] and "name" in err["loc"]


def test_field_name_duplicate() -> None:
    data = load_sample_config()
    data["fields"][1]["name"] = data["fields"][0]["name"]
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("fields" in str(err["loc"]) for err in exc.value.errors())


def test_derived_name_duplicate_with_field() -> None:
    data = load_sample_config()
    data["derived"][0]["name"] = data["fields"][0]["name"]
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("derived" in str(err["loc"]) for err in exc.value.errors())


def test_derived_expr_unknown_function() -> None:
    data = load_sample_config()
    data["derived"][0]["expr"]["fn"] = "unknown_func"
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("fn" in str(err["loc"]) for err in exc.value.errors())


def test_db_source_table_required_when_kind_is_table() -> None:
    data = load_sample_config()
    data["db_source"]["kind"] = "table"
    data["db_source"]["table"] = None
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("db_source" in str(err["loc"]) and "table" in str(err["loc"]) for err in exc.value.errors())


def test_db_source_missing_p_from_param() -> None:
    data = load_sample_config()
    data["db_source"]["params"] = [p for p in data["db_source"]["params"] if p["name"] != "p_from"]
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("db_source" in str(err["loc"]) and "params" in str(err["loc"]) for err in exc.value.errors())


def test_db_source_missing_p_to_param() -> None:
    data = load_sample_config()
    data["db_source"]["params"] = [p for p in data["db_source"]["params"] if p["name"] != "p_to"]
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("db_source" in str(err["loc"]) and "params" in str(err["loc"]) for err in exc.value.errors())


def test_db_source_p_from_must_be_user_source() -> None:
    data = load_sample_config()
    for p in data["db_source"]["params"]:
        if p["name"] == "p_from":
            p["source"] = "default"
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("p_from" in str(err["loc"]) or "params" in str(err["loc"]) for err in exc.value.errors())


def test_db_source_table_missing_filter_for_p_from() -> None:
    data = load_sample_config()
    data["db_source"]["filters"] = [f for f in data["db_source"]["filters"] if f["param"] != "p_from"]
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("db_source" in str(err["loc"]) and "filters" in str(err["loc"]) for err in exc.value.errors())


def test_db_source_table_missing_filter_for_p_to() -> None:
    data = load_sample_config()
    data["db_source"]["filters"] = [f for f in data["db_source"]["filters"] if f["param"] != "p_to"]
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("db_source" in str(err["loc"]) and "filters" in str(err["loc"]) for err in exc.value.errors())


def test_time_filter_nonexistent_excel_field() -> None:
    data = load_sample_config()
    data["time_filter"]["excel_field"] = "NONEXISTENT_FIELD"
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("time_filter" in str(err["loc"]) and "excel_field" in str(err["loc"]) for err in exc.value.errors())


def test_profiles_must_have_exactly_one_default() -> None:
    # 0 default
    data = load_sample_config()
    for prof in data["profiles"]:
        prof["is_default"] = False
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("profiles" in str(err["loc"]) for err in exc.value.errors())

    # 2 defaults
    data = load_sample_config()
    data["profiles"][0]["is_default"] = True
    data["profiles"][1]["is_default"] = True
    with pytest.raises(ValidationError) as exc2:
        TemplateConfig.model_validate(data)
    assert any("profiles" in str(err["loc"]) for err in exc2.value.errors())


def test_profile_group_by_field_not_found() -> None:
    data = load_sample_config()
    data["profiles"][0]["group_by"] = ["UNKNOWN_FIELD"]
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("profiles" in str(err["loc"]) and "group_by" in str(err["loc"]) for err in exc.value.errors())


def test_profile_group_by_field_not_in_db() -> None:
    # SERVICE_NAME chỉ có ở Excel (db=None), không thể group_by
    data = load_sample_config()
    data["profiles"][0]["group_by"] = ["SERVICE_NAME"]
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("profiles" in str(err["loc"]) and "group_by" in str(err["loc"]) for err in exc.value.errors())


def test_profile_measure_field_not_found() -> None:
    data = load_sample_config()
    data["profiles"][0]["measures"][0]["field"] = "NOT_A_FIELD"
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("profiles" in str(err["loc"]) and "measures" in str(err["loc"]) for err in exc.value.errors())


def test_profile_measure_sum_on_non_number() -> None:
    # STATUS là kiểu text, không thể sum
    data = load_sample_config()
    data["profiles"][0]["measures"][0]["field"] = "STATUS"
    data["profiles"][0]["measures"][0]["agg"] = "sum"
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("measures" in str(err["loc"]) and "agg" in str(err["loc"]) for err in exc.value.errors())


def test_profile_measure_value_only_allowed_when_not_aggregate() -> None:
    # profiles[0].aggregate = True, không được agg="value"
    data = load_sample_config()
    data["profiles"][0]["measures"][0]["agg"] = "value"
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("measures" in str(err["loc"]) and "agg" in str(err["loc"]) for err in exc.value.errors())


def test_profile_main_measure_must_exist_in_measures() -> None:
    data = load_sample_config()
    data["profiles"][0]["main_measure"] = "NONEXISTENT_MEASURE"
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any("profiles" in str(err["loc"]) and "main_measure" in str(err["loc"]) for err in exc.value.errors())


def test_profile_drilldown_cycle_detected() -> None:
    data = load_sample_config()
    # BY_INVOICE -> BY_LINE -> BY_INVOICE (cycle)
    for p in data["profiles"]:
        if p["code"] == "BY_INVOICE":
            p["drilldown_to"] = "BY_LINE"
        elif p["code"] == "BY_LINE":
            p["drilldown_to"] = "BY_INVOICE"
    with pytest.raises(ValidationError) as exc:
        TemplateConfig.model_validate(data)
    assert any(
        "drilldown" in str(err["msg"]).lower() or "drilldown" in str(err["loc"]).lower() for err in exc.value.errors()
    )
