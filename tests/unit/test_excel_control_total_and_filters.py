from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from app.engine.control_total import ControlTotalResult, check_control_total
from app.engine.filters import TimeFilterResult, apply_row_filters, apply_time_filter
from app.engine.mapping import resolve_columns
from app.engine.normalize import normalize
from app.engine.reader import read_sheet
from app.schemas.template_config import (
    ControlTotalLocate,
    ControlTotalSpec,
    RowFilter,
    RowFilters,
    TemplateConfig,
)


@pytest.fixture
def dtp_template() -> TemplateConfig:
    import json

    path = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return TemplateConfig.model_validate(data)


def test_control_total_dtp_sample(dtp_template: TemplateConfig) -> None:
    path = Path("samples/dtp_sample_200.xlsx")
    raw_df, _ = read_sheet(path, dtp_template.file)

    # Dòng tổng có 'Tổng tiền' ở cột 'Dịch vụ'
    assert dtp_template.control_total is not None

    # Lọc bỏ dòng tổng trước khi normalize để có valid_df dữ liệu thật
    filtered_df = apply_row_filters(raw_df, dtp_template.file.row_filters)
    mapped_df, _ = resolve_columns(filtered_df, dtp_template.fields)
    valid_df, invalid_rows = normalize(mapped_df, dtp_template.fields)
    assert len(invalid_rows) == 0
    assert len(valid_df) == 200

    result = check_control_total(
        raw_df=raw_df,
        valid_df=valid_df,
        spec=dtp_template.control_total,
        fields=dtp_template.fields,
    )

    assert isinstance(result, ControlTotalResult)
    assert result.is_matched is True
    assert result.file_total == Decimal("366732000")
    assert result.calc_total == Decimal("366732000")
    assert result.diff == Decimal("0")
    assert result.located_row_no == 202
    assert result.warning is None


def test_control_total_tolerance_and_mismatch() -> None:
    raw_df = pl.DataFrame(
        {
            "__row_no": [1, 2, 3],
            "LABEL": ["A", "B", "TOTAL"],
            "VAL": ["100", "200", "310"],
        }
    )
    valid_df = pl.DataFrame(
        {
            "__row_no": [1, 2],
            "AMOUNT": [Decimal("100"), Decimal("200")],
        }
    )
    spec = ControlTotalSpec(
        locate=ControlTotalLocate(excel_col="LABEL", equals="TOTAL"),
        value_col="VAL",
        tolerance=5,
    )
    # diff = |300 - 310| = 10 > tolerance 5 -> False
    res1 = check_control_total(raw_df, valid_df, spec)
    assert res1.is_matched is False
    assert res1.diff == Decimal("10")
    assert res1.file_total == Decimal("310")
    assert res1.calc_total == Decimal("300")

    # With tolerance 15 -> True
    spec_tol = ControlTotalSpec(
        locate=ControlTotalLocate(excel_col="LABEL", equals="TOTAL"),
        value_col="VAL",
        tolerance=15,
    )
    res2 = check_control_total(raw_df, valid_df, spec_tol)
    assert res2.is_matched is True


def test_control_total_not_found() -> None:
    raw_df = pl.DataFrame(
        {
            "__row_no": [1, 2],
            "LABEL": ["A", "B"],
            "VAL": ["100", "200"],
        }
    )
    valid_df = pl.DataFrame(
        {
            "__row_no": [1, 2],
            "VAL": [Decimal("100"), Decimal("200")],
        }
    )
    spec = ControlTotalSpec(
        locate=ControlTotalLocate(excel_col="LABEL", equals="TOTAL_NOT_EXISTS"),
        value_col="VAL",
    )
    res = check_control_total(raw_df, valid_df, spec)
    assert res.is_matched is False
    assert res.file_total is None
    assert res.calc_total == Decimal("300")
    assert res.warning == "CONTROL_TOTAL_NOT_FOUND"


def test_row_filters_drop_if_null(dtp_template: TemplateConfig) -> None:
    path = Path("samples/dtp_sample_200.xlsx")
    raw_df, _ = read_sheet(path, dtp_template.file)
    assert len(raw_df) == 201

    filtered_df = apply_row_filters(raw_df, dtp_template.file.row_filters)
    assert len(filtered_df) == 200
    # Dòng 202 (Số hóa đơn None) đã bị loại bỏ
    assert 202 not in filtered_df["__row_no"].to_list()


def test_row_filters_keep_if_and_ops() -> None:
    df = pl.DataFrame(
        {
            "__row_no": [1, 2, 3, 4, 5],
            "STATUS": ["ACTIVE", "INACTIVE", "PENDING", "", None],
            "CODE": ["A10", "B20", "A30", "C40", "D50"],
        }
    )
    # drop_if regex: starts with B
    filters = RowFilters(
        drop_if=[RowFilter(excel_col="CODE", op="regex", value=r"^B")],
        keep_if=[RowFilter(excel_col="STATUS", op="not_null")],
    )
    filtered = apply_row_filters(df, filters)
    assert filtered["__row_no"].to_list() == [1, 3]


def test_time_filter_dtp_sample(dtp_template: TemplateConfig) -> None:
    path = Path("samples/dtp_sample_200.xlsx")
    raw_df, _ = read_sheet(path, dtp_template.file)
    filtered_df = apply_row_filters(raw_df, dtp_template.file.row_filters)
    mapped_df, _ = resolve_columns(filtered_df, dtp_template.fields)
    valid_df, _ = normalize(mapped_df, dtp_template.fields)

    time_filter = dtp_template.time_filter
    assert time_filter is not None

    # Toàn bộ khoảng (01/02/2026 - 05/02/2026) -> cả 200 dòng đều hợp lệ
    res_full = apply_time_filter(
        valid_df,
        time_filter=time_filter,
        p_from=datetime(2026, 2, 1, 0, 0, 0),
        p_to=datetime(2026, 2, 5, 23, 59, 59),
    )
    assert isinstance(res_full, TimeFilterResult)
    assert len(res_full.df) == 200
    assert res_full.out_of_range_count == 0
    assert len(res_full.out_of_range_row_nos) == 0

    # Lọc hẹp: 01/02/2026 00:00:00 -> 02/02/2026 23:59:59
    res_narrow = apply_time_filter(
        valid_df,
        time_filter=time_filter,
        p_from=datetime(2026, 2, 1, 0, 0, 0),
        p_to=datetime(2026, 2, 2, 23, 59, 59),
    )
    assert len(res_narrow.df) < 200
    assert res_narrow.out_of_range_count > 0
    assert len(res_narrow.df) + res_narrow.out_of_range_count == 200
    assert len(res_narrow.out_of_range_row_nos) == res_narrow.out_of_range_count
