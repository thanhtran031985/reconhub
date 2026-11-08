from __future__ import annotations

from pathlib import Path

from app.engine.inspect import CandidateTotalRow, ColumnInspection, FileInspectionResult, inspect_sample


def test_inspect_dtp_sample() -> None:
    path = Path("samples/dtp_sample_200.xlsx")
    res = inspect_sample(path)

    assert isinstance(res, FileInspectionResult)
    assert res.sheet == "BÁO CÁO DTP"
    assert "BÁO CÁO DTP" in res.sheets
    assert res.total_rows >= 201
    assert res.total_cols >= 18

    # Kiểm tra dòng tổng ứng viên
    assert len(res.candidate_total_rows) >= 1
    total_row = res.candidate_total_rows[0]
    assert isinstance(total_row, CandidateTotalRow)
    assert total_row.row_no == 202
    assert "tổng" in total_row.label_val.lower()
    assert total_row.values.get("Thành tiền") in ("366732000", "366732000.0", "366,732,000")

    # Kiểm tra gợi ý cột
    col_map = {c.name: c for c in res.columns}
    assert "Số hóa đơn" in col_map
    inv_col = col_map["Số hóa đơn"]
    assert isinstance(inv_col, ColumnInspection)
    assert inv_col.suggested_field_name == "SO_HOA_DON"
    assert inv_col.suggested_type == "text"
    assert inv_col.is_candidate_key is True

    date_col = col_map["Ngày lập hóa đơn"]
    assert date_col.suggested_field_name == "NGAY_LAP_HOA_DON"
    assert date_col.suggested_type in ("date", "datetime")
    assert date_col.is_date is True

    amt_col = col_map["Thành tiền"]
    assert amt_col.suggested_field_name == "THANH_TIEN"
    assert amt_col.suggested_type == "number"


def test_inspect_leading_zero_and_mixed() -> None:
    import tempfile

    import polars as pl

    df = pl.DataFrame(
        {
            "Mã số thuế": ["0304422444-021", "0334", "0123456789"],
            "Ghi chú lẫn lộn": ["100", "ABC", "200"],
            "Điểm": ["10.5", "20.0", "30.25"],
        }
    )
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        tmp_path = Path(f.name)
    try:
        df.write_csv(tmp_path)
        res = inspect_sample(tmp_path)

        col_map = {c.name: c for c in res.columns}
        mst = col_map["Mã số thuế"]
        assert mst.suggested_field_name == "MA_SO_THUE"
        assert mst.has_leading_zero is True
        assert mst.suggested_type == "text"

        note = col_map["Ghi chú lẫn lộn"]
        assert note.suggested_field_name == "GHI_CHU_LAN_LON"
        assert note.has_mixed_types is True
        assert note.suggested_type == "text"

        score = col_map["Điểm"]
        assert score.suggested_field_name == "DIEM"
        assert score.suggested_type == "number"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_inspect_title_banner_detection() -> None:
    """Kiểm tra tự phát hiện dòng tiêu đề khi có dòng banner ở trên cùng."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
        f.write("Báo cáo doanh thu tháng 7,,,\n")
        f.write("Số HĐ,Ngày HĐ,Thành tiền,Ghi chú\n")
        f.write("HD001,01/07/2026,1000000,Gốc\n")
        f.write("HD002,02/07/2026,2000000,Gốc\n")
        tmp_path = Path(f.name)

    try:
        res = inspect_sample(tmp_path)
        assert res.suggested_header_row == 2
        assert res.suggested_data_start_row == 3
        col_names = [c.name for c in res.columns]
        assert "Số HĐ" in col_names
        assert "Thành tiền" in col_names
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

