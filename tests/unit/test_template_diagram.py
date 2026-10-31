from __future__ import annotations

import json
from pathlib import Path

from app.schemas.template_config import TemplateConfig
from app.services.diagram import (
    generate_all_diagrams,
    generate_control_total_diagram,
    generate_db_query_diagram,
    generate_fields_normalization_diagram,
    generate_pipeline_diagram,
    generate_profiles_hierarchy_diagram,
)

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_sample_config() -> TemplateConfig:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TemplateConfig.model_validate(data)


def test_generate_pipeline_diagram() -> None:
    cfg = get_sample_config()
    diagram = generate_pipeline_diagram(cfg)
    assert diagram.startswith("flowchart LR")
    assert "Excel" in diagram
    assert "RECON_SRC.SRC_FACT_INVOICE_DTP" in diagram or "BÁO CÁO DTP" in diagram


def test_generate_fields_normalization_diagram() -> None:
    cfg = get_sample_config()
    diagram = generate_fields_normalization_diagram(cfg)
    assert diagram.startswith("flowchart")
    assert "INVOICE_NO" in diagram
    assert "trim" in diagram.lower()


def test_generate_db_query_diagram() -> None:
    cfg = get_sample_config()
    diagram = generate_db_query_diagram(cfg)
    assert diagram.startswith("flowchart")
    assert "p_from" in diagram
    assert "p_to" in diagram
    assert "INVOICE_DATE" in diagram


def test_generate_profiles_hierarchy_diagram() -> None:
    cfg = get_sample_config()
    diagram = generate_profiles_hierarchy_diagram(cfg)
    assert diagram.startswith("flowchart")
    assert "BY_INVOICE" in diagram
    assert "BY_LINE" in diagram
    # Drilldown link
    assert "-->" in diagram


def test_generate_control_total_diagram() -> None:
    cfg = get_sample_config()
    diagram = generate_control_total_diagram(cfg)
    assert diagram.startswith("flowchart")
    assert "Tổng tiền" in diagram
    assert "Thành tiền" in diagram


def test_generate_all_diagrams_returns_all_five() -> None:
    cfg = get_sample_config()
    all_diagrams = generate_all_diagrams(cfg)
    assert set(all_diagrams.keys()) == {
        "pipeline",
        "normalization",
        "db_query",
        "profiles",
        "control_total",
    }
    for _k, v in all_diagrams.items():
        assert len(v.strip()) > 0
