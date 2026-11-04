from __future__ import annotations

from app.ui.pages.new_run import (
    build_extra_params_dict,
    extra_run_params,
    missing_required_extra_params,
    render_params_section,
    sync_extra_params_on_template_change,
)


def _template_with_application() -> dict:
    return {
        "id": 1,
        "code": "VTOS",
        "config": {
            "profiles": [{"code": "BY_INVOICE_VTOS", "name": "Theo số hóa đơn", "is_default": True}],
            "db_source": {
                "params": [
                    {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
                    {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
                    {"name": "p_org", "type": "text", "source": "default", "default": "BDP", "label": "Đơn vị"},
                    {
                        "name": "p_application",
                        "type": "text",
                        "source": "default",
                        "default": "VTOS",
                        # Nhãn mặc định wizard tự gán khi thêm tham số mới;
                        # /runs/new không được hiển thị nhãn này.
                        "label": "Tham Số 1",
                    },
                ]
            },
        },
    }


def test_extra_run_params_excludes_fixed_params_and_keeps_order() -> None:
    params = extra_run_params(_template_with_application()["config"])
    assert [p["name"] for p in params] == ["p_application"]


def test_render_params_section_shows_p_application_input() -> None:
    ui = render_params_section(
        template_info=_template_with_application(),
        data_sources=[],
        active_templates=[],
    )
    text = str(ui)
    assert "new-run-extra-params" in text
    assert "p_application" in text
    assert "VTOS" in text


def test_sync_extra_params_on_template_change_renders_application() -> None:
    children = sync_extra_params_on_template_change(_template_with_application())
    assert len(children) == 1
    assert children[0].id == {"type": "new-run-extra-param", "name": "p_application"}
    assert children[0].value == "VTOS"
    # Nhãn lấy theo tên parameter, không lấy label "Tham Số 1" của wizard,
    # để thêm nhiều tham số một lúc vẫn phân biệt được ô nào là gì.
    assert children[0].label == "p_application"


def test_render_params_section_label_is_param_name_not_generic_label() -> None:
    ui = render_params_section(
        template_info=_template_with_application(),
        data_sources=[],
        active_templates=[],
    )
    assert "p_application" in str(ui)
    assert "Tham Số 1" not in str(ui)


def test_build_extra_params_dict_maps_values_in_order_and_skips_empty() -> None:
    tmpl = _template_with_application()
    assert build_extra_params_dict(tmpl, ["VTOS"]) == {"p_application": "VTOS"}
    assert build_extra_params_dict(tmpl, [""]) == {}
    assert build_extra_params_dict(tmpl, []) == {}


def test_missing_required_extra_params_only_when_no_default_and_empty() -> None:
    tmpl = _template_with_application()
    # p_application có default VTOS nên bỏ trống cũng không tính là thiếu.
    assert missing_required_extra_params(tmpl, [""]) == []
    tmpl["config"]["db_source"]["params"][3]["required"] = True
    tmpl["config"]["db_source"]["params"][3]["default"] = None
    assert missing_required_extra_params(tmpl, [""]) == ["p_application"]
    assert missing_required_extra_params(tmpl, ["VTOS"]) == []
