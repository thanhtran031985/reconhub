from __future__ import annotations

from pathlib import Path

from app.engine.reader import list_sheets, read_sheet
from app.schemas.template_config import FileSpec

SAMPLE_XLSX = Path("samples/dtp_sample_200.xlsx")


def test_list_sheets_excel() -> None:
    sheets = list_sheets(SAMPLE_XLSX)
    assert len(sheets) == 1
    assert sheets[0] == "BÁO CÁO DTP"


def test_read_sheet_dtp_sample() -> None:
    file_spec = FileSpec(
        sheet="BÁO CÁO DTP",
        header_row=1,
        data_start_row=2,
        skip_footer_rows=0,
    )
    df, warnings = read_sheet(SAMPLE_XLSX, file_spec)

    # File có 1 dòng header + 200 dòng dữ liệu + 1 dòng tổng = 201 dòng dữ liệu thô
    assert df.height == 201
    assert "__row_no" in df.columns

    # Dòng đầu tiên có __row_no = 2
    assert df["__row_no"][0] == 2
    # Dòng cuối cùng có __row_no = 202
    assert df["__row_no"][-1] == 202

    # Kiểm tra cột Mã giao dịch được giữ nguyên dạng chuỗi
    assert "Mã giao dịch" in df.columns
    txn_id = df["Mã giao dịch"][0]
    assert isinstance(txn_id, str)
    assert "PAYMENTGW" in txn_id


def test_read_sheet_duplicate_headers_handling(tmp_path) -> None:
    # Tạo file CSV có header trùng lặp
    csv_file = tmp_path / "test_dup_headers.csv"
    csv_file.write_text("ID,NAME,NAME,AMOUNT\n1,Alpha,Beta,100\n2,Gamma,Delta,200\n", encoding="utf-8")

    file_spec = FileSpec(sheet="Sheet1", header_row=1, data_start_row=2)
    df, warnings = read_sheet(csv_file, file_spec)

    assert df.height == 2
    assert "NAME" in df.columns
    assert "NAME__2" in df.columns
    assert any("trùng" in w.lower() for w in warnings)
    assert df["NAME"][0] == "Alpha"
    assert df["NAME__2"][0] == "Beta"


def test_read_csv_with_semicolon_and_utf8_sig(tmp_path) -> None:
    # Golden G12: CSV phân cách bằng ';' và UTF-8 with BOM
    csv_file = tmp_path / "test_semicolon.csv"
    csv_content = "\ufeffSố hóa đơn;Mã số;Số tiền\n0123;00987;500000\n0124;00988;600000\n"
    csv_file.write_bytes(csv_content.encode("utf-8-sig"))

    file_spec = FileSpec(sheet="Sheet1", header_row=1, data_start_row=2)
    df, warnings = read_sheet(csv_file, file_spec)

    assert df.height == 2
    assert df["Số hóa đơn"][0] == "0123"  # Giữ nguyên số 0 ở đầu (G03)
    assert df["Mã số"][0] == "00987"
    assert df["__row_no"][0] == 2
