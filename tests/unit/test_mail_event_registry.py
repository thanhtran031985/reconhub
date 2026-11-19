"""Unit tests for Mail Event Registry."""

from __future__ import annotations

from app.engine.mail_event_registry import (
    EVENT_BATCH_RUN,
    extract_variable_keys,
    get_allowed_variable_keys,
    get_event_definition,
    get_sample_payload,
    list_event_definitions,
    validate_text_variables,
)


def test_list_and_get_event_definitions():
    events = list_event_definitions()
    assert len(events) >= 4
    codes = {e.code for e in events}
    assert "BATCH_RUN_COMPLETED" in codes
    assert "REPORT_EXPORT_COMPLETED" in codes
    assert "TEMPLATE_LIST_EXPORT" in codes
    assert "GENERAL_EXPORT" in codes

    assert get_event_definition("BATCH_RUN_COMPLETED") == EVENT_BATCH_RUN
    assert get_event_definition("NON_EXISTING") is None


def test_event_variables_and_allowed_keys():
    batch_keys = get_allowed_variable_keys("BATCH_RUN_COMPLETED")
    assert "actor.name" in batch_keys
    assert "batch.name" in batch_keys
    assert "summary.failed" in batch_keys
    assert "links.result" in batch_keys

    report_keys = get_allowed_variable_keys("REPORT_EXPORT_COMPLETED")
    assert "export.filename" in report_keys
    assert "export.rows" in report_keys


def test_extract_variable_keys():
    text = "Xin chào {{ actor.name }}, mã phiên {{batch.run_code}} có {{ summary.failed }} lỗi."
    keys = extract_variable_keys(text)
    assert keys == ["actor.name", "batch.run_code", "summary.failed"]

    empty_keys = extract_variable_keys("Không có biến nào ở đây.")
    assert empty_keys == []


def test_validate_text_variables():
    # Đúng schema
    valid_text = "Chào {{actor.name}}, kết quả: {{summary.total}}"
    violations = validate_text_variables(valid_text, "BATCH_RUN_COMPLETED")
    assert violations == []

    # Biến không thuộc event
    invalid_text = "Chào {{actor.name}}, file: {{export.filename}}, foo: {{unknown_var}}"
    violations = validate_text_variables(invalid_text, "BATCH_RUN_COMPLETED")
    assert "export.filename" in violations
    assert "unknown_var" in violations


def test_sample_payload_scenarios():
    for event_code in ["BATCH_RUN_COMPLETED", "REPORT_EXPORT_COMPLETED", "TEMPLATE_LIST_EXPORT", "GENERAL_EXPORT"]:
        success = get_sample_payload(event_code, "success")
        error = get_sample_payload(event_code, "error")
        empty = get_sample_payload(event_code, "empty")

        assert isinstance(success, dict) and len(success) > 0
        assert isinstance(error, dict) and len(error) > 0
        assert isinstance(empty, dict) and len(empty) > 0

    # Fallback to success when unknown scenario
    default = get_sample_payload("BATCH_RUN_COMPLETED", "unknown_scenario")
    assert default == get_sample_payload("BATCH_RUN_COMPLETED", "success")
