from __future__ import annotations

import html
import io
import zipfile
from datetime import datetime
from typing import Any

import xlsxwriter

from app.engine.export_styles import get_export_formats


def _format_dt(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y %H:%M:%S")
    return str(val)


def _format_profiles(profiles: list[dict[str, Any]] | None) -> str:
    if not profiles:
        return "—"
    parts: list[str] = []
    for p in profiles:
        name = p.get("name") or p.get("profile_id") or p.get("code") or ""
        is_def = bool(p.get("is_default", False))
        parts.append(f"{name} (mặc định)" if is_def else name)
    return ", ".join(parts)


def _format_last_run(last_run: dict[str, Any] | None) -> str:
    if not last_run:
        return "Chưa chạy"
    rid = last_run.get("id", "")
    st = last_run.get("status", "")
    f_at = last_run.get("finished_at", "")
    if f_at:
        return f"#{rid} · {st} ({f_at})"
    return f"#{rid} · {st}"


def build_templates_list_excel(
    items: list[dict[str, Any]],
    exported_by: str = "admin",
    filters_info: str = "",
) -> bytes:
    """Tạo file Excel (.xlsx) danh sách template bằng XlsxWriter."""
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = wb.add_worksheet("Danh sách Template")

    ws.set_landscape()
    ws.set_paper(9)  # A4
    ws.fit_to_pages(1, 0)
    ws.hide_gridlines(False)

    formats = get_export_formats(wb)
    title_fmt = formats["title"]
    text_fmt = formats["text"]
    key_text_fmt = formats["key_text"]
    text_center_fmt = formats["text_center"]
    int_fmt = formats["number_integer"]
    header_fmt = formats["table_header"]

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Title & Metadata
    ws.write(0, 0, "DANH SÁCH TEMPLATE ĐỐI SOÁT — RECONHUB", title_fmt)
    ws.set_row(0, 24)

    meta_text = f"Ngày xuất: {now_str} | Người xuất: @{exported_by} | Tổng số: {len(items)} template"
    if filters_info:
        meta_text += f" | {filters_info}"
    ws.write(1, 0, meta_text, text_fmt)
    ws.set_row(1, 18)

    headers = [
        ("STT", 6, text_center_fmt),
        ("Mã template", 20, key_text_fmt),
        ("Tên template", 30, text_fmt),
        ("Nhận diện file", 25, text_fmt),
        ("Sheet", 15, text_fmt),
        ("Số trường", 12, int_fmt),
        ("Profiles đối soát", 32, text_fmt),
        ("Phiên bản", 10, text_center_fmt),
        ("Chủ sở hữu", 14, text_fmt),
        ("Trạng thái", 14, text_center_fmt),
        ("Run gần nhất", 24, text_fmt),
        ("Ngày tạo", 18, text_center_fmt),
        ("Ngày cập nhật", 18, text_center_fmt),
    ]

    header_row = 3
    ws.set_row(header_row, 24)
    for col_idx, (col_name, col_width, _) in enumerate(headers):
        ws.write(header_row, col_idx, col_name, header_fmt)
        ws.set_column(col_idx, col_idx, col_width)

    # Freeze header row
    ws.freeze_panes(header_row + 1, 0)

    # Data rows
    row_idx = header_row + 1
    if not items:
        ws.write(row_idx, 0, 1, text_center_fmt)
        ws.write(row_idx, 1, "—", text_fmt)
        ws.write(row_idx, 2, "Chưa có template nào", text_fmt)
        for c in range(3, len(headers)):
            ws.write(row_idx, c, "—", text_center_fmt)
    else:
        for idx, it in enumerate(items, start=1):
            ws.set_row(row_idx, 20)
            ws.write(row_idx, 0, idx, text_center_fmt)
            ws.write(row_idx, 1, it.get("code") or it.get("template_id") or "", key_text_fmt)
            ws.write(row_idx, 2, it.get("name") or "", text_fmt)
            ws.write(row_idx, 3, it.get("file_pattern") or "—", text_fmt)
            ws.write(row_idx, 4, it.get("sheet") or "—", text_fmt)
            ws.write(row_idx, 5, int(it.get("field_count") or 0), int_fmt)
            ws.write(row_idx, 6, _format_profiles(it.get("profiles")), text_fmt)
            ws.write(row_idx, 7, f"v{it.get('current_version') or it.get('version', 1)}", text_center_fmt)
            ws.write(row_idx, 8, f"@{it.get('owner') or it.get('created_by') or ''}", text_fmt)
            ws.write(row_idx, 9, str(it.get("status") or ""), text_center_fmt)
            ws.write(row_idx, 10, _format_last_run(it.get("last_run")), text_fmt)
            ws.write(row_idx, 11, _format_dt(it.get("created_at")), text_center_fmt)
            ws.write(row_idx, 12, _format_dt(it.get("updated_at")), text_center_fmt)
            row_idx += 1

    wb.close()
    output.seek(0)
    return output.getvalue()


def build_templates_list_docx(
    items: list[dict[str, Any]],
    exported_by: str = "admin",
    filters_info: str = "",
) -> bytes:
    """Tạo file Microsoft Word (.docx) chuẩn OpenXML landscape."""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI" w:cs="Segoe UI"/>
        <w:sz w:val="18"/>
        <w:color w:val="2D3748"/>
      </w:rPr>
    </w:rPrDefault>
  </w:docDefaults>
</w:styles>"""

    def esc(s: Any) -> str:
        if s is None:
            return ""
        return html.escape(str(s))

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    headers = [
        ("STT", "500", "center"),
        ("Mã template", "2100", "left"),
        ("Tên template", "2600", "left"),
        ("Nhận diện file", "2100", "left"),
        ("Số trường", "900", "center"),
        ("Profiles", "2200", "left"),
        ("Phiên bản", "900", "center"),
        ("Chủ sở hữu", "1200", "left"),
        ("Trạng thái", "1200", "center"),
        ("Run gần nhất", "1900", "left"),
    ]

    rows_xml: list[str] = []

    # Table Header Row
    th_cells: list[str] = []
    for h, width, align in headers:
        th_cells.append(f"""
        <w:tc>
          <w:tcPr>
            <w:tcW w:w="{width}" w:type="dxa"/>
            <w:shd w:val="clear" w:color="auto" w:fill="F1F3F5"/>
            <w:tcMar><w:top w:w="120" w:type="dxa"/><w:bottom w:w="120" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>
          </w:tcPr>
          <w:p>
            <w:pPr><w:jc w:val="{align}"/></w:pPr>
            <w:r><w:rPr><w:b/><w:sz w:val="17"/><w:color w:val="1F2937"/></w:rPr><w:t>{esc(h)}</w:t></w:r>
          </w:p>
        </w:tc>""")
    rows_xml.append(f"<w:tr><w:trPr><w:tblHeader/></w:trPr>{''.join(th_cells)}</w:tr>")

    # Data Rows
    if not items:
        empty_cells = f"""
        <w:tc>
          <w:tcPr>
            <w:gridSpan w:val="{len(headers)}"/>
            <w:tcMar><w:top w:w="140" w:type="dxa"/><w:bottom w:w="140" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>
          </w:tcPr>
          <w:p>
            <w:pPr><w:jc w:val="center"/></w:pPr>
            <w:r><w:rPr><w:i/><w:color w:val="6B7280"/></w:rPr><w:t>Không có template nào phù hợp</w:t></w:r>
          </w:p>
        </w:tc>"""
        rows_xml.append(f"<w:tr>{empty_cells}</w:tr>")
    else:
        for idx, it in enumerate(items, start=1):
            tid = it.get("code") or it.get("template_id") or ""
            tname = it.get("name") or ""
            fpattern = it.get("file_pattern") or "—"
            fcount = str(it.get("field_count") or 0)
            profiles_str = _format_profiles(it.get("profiles"))
            version_str = f"v{it.get('current_version') or it.get('version', 1)}"
            owner_str = f"@{it.get('owner') or it.get('created_by') or ''}"
            status_str = str(it.get("status") or "")
            last_run_str = _format_last_run(it.get("last_run"))

            row_data = [
                (str(idx), "center", False),
                (tid, "left", True),
                (tname, "left", False),
                (fpattern, "left", False),
                (fcount, "center", False),
                (profiles_str, "left", False),
                (version_str, "center", False),
                (owner_str, "left", False),
                (status_str, "center", False),
                (last_run_str, "left", False),
            ]

            td_cells: list[str] = []
            for col_idx, (val, align, is_bold) in enumerate(row_data):
                w = headers[col_idx][1]
                bold_tag = "<w:b/>" if is_bold else ""
                td_cells.append(f"""
                <w:tc>
                  <w:tcPr>
                    <w:tcW w:w="{w}" w:type="dxa"/>
                    <w:tcMar><w:top w:w="90" w:type="dxa"/><w:bottom w:w="90" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>
                  </w:tcPr>
                  <w:p>
                    <w:pPr><w:jc w:val="{align}"/></w:pPr>
                    <w:r><w:rPr>{bold_tag}<w:sz w:val="17"/></w:rPr><w:t>{esc(val)}</w:t></w:r>
                  </w:p>
                </w:tc>""")
            rows_xml.append(f"<w:tr>{''.join(td_cells)}</w:tr>")

    meta_line = f"Ngày xuất: {now_str} · Người xuất: @{exported_by} · Tổng số: {len(items)} template"
    if filters_info:
        meta_line += f" · {filters_info}"

    doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:spacing w:after="120"/></w:pPr>
      <w:r><w:rPr><w:b/><w:sz w:val="30"/><w:color w:val="0F172A"/></w:rPr><w:t>DANH SÁCH TEMPLATE ĐỐI SOÁT — RECONHUB</w:t></w:r>
    </w:p>
    <w:p>
      <w:pPr><w:spacing w:after="220"/></w:pPr>
      <w:r><w:rPr><w:sz w:val="18"/><w:color w:val="64748B"/></w:rPr><w:t>{esc(meta_line)}</w:t></w:r>
    </w:p>
    <w:tbl>
      <w:tblPr>
        <w:tblW w:w="0" w:type="auto"/>
        <w:tblBorders>
          <w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
          <w:insideV w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
        </w:tblBorders>
      </w:tblPr>
      {"".join(rows_xml)}
    </w:tbl>
    <w:sectPr>
      <w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>
      <w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", styles_xml)
        z.writestr("word/document.xml", doc_xml)

    buf.seek(0)
    return buf.getvalue()


def build_templates_list_pdf(
    items: list[dict[str, Any]],
    exported_by: str = "admin",
    filters_info: str = "",
) -> bytes:
    """Tạo file PDF chuẩn A4 landscape qua Playwright Chromium headless."""
    from playwright.sync_api import sync_playwright

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    meta_line = (
        f"Ngày xuất: {now_str} &middot; Người xuất: @{html.escape(exported_by)} &middot; Tổng số: {len(items)} template"
    )
    if filters_info:
        meta_line += f" &middot; {html.escape(filters_info)}"

    rows_html: list[str] = []
    if not items:
        rows_html.append(
            '<tr><td colspan="10" style="text-align: center; padding: 20px; color: #64748b;">Không có template nào phù hợp</td></tr>'
        )
    else:
        for idx, it in enumerate(items, start=1):
            tid = html.escape(str(it.get("code") or it.get("template_id") or ""))
            tname = html.escape(str(it.get("name") or ""))
            fpattern = html.escape(str(it.get("file_pattern") or "—"))
            fcount = str(it.get("field_count") or 0)
            profiles_str = html.escape(_format_profiles(it.get("profiles")))
            version_str = f"v{it.get('current_version') or it.get('version', 1)}"
            owner_str = f"@{html.escape(str(it.get('owner') or it.get('created_by') or ''))}"
            status_val = str(it.get("status") or "")
            status_color = "#16A34A" if status_val == "ACTIVE" else "#D97706" if status_val == "DRAFT" else "#64748B"
            status_badge = f'<span style="display:inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; color: #fff; background-color: {status_color};">{status_val}</span>'
            last_run_str = html.escape(_format_last_run(it.get("last_run")))

            rows_html.append(f"""
            <tr>
              <td style="text-align: center;">{idx}</td>
              <td style="font-family: monospace; font-weight: 700; color: #1e293b;">{tid}</td>
              <td><strong>{tname}</strong></td>
              <td style="color: #475569; font-size: 11px;">{fpattern}</td>
              <td style="text-align: center;"><span style="background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{fcount} trường</span></td>
              <td style="font-size: 11px; color: #334155;">{profiles_str}</td>
              <td style="text-align: center; font-size: 11px; color: #64748b;">{version_str}</td>
              <td style="color: #64748b;">{owner_str}</td>
              <td style="text-align: center;">{status_badge}</td>
              <td style="font-size: 11px; color: #475569;">{last_run_str}</td>
            </tr>
            """)

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="utf-8">
    <title>Danh sách Template — ReconHub</title>
    <style>
        @page {{
            size: A4 landscape;
            margin: 10mm 12mm 12mm 12mm;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            color: #1e293b;
            font-size: 12px;
            background: #ffffff;
        }}
        .header {{
            margin-bottom: 16px;
            border-bottom: 2px solid #0284c7;
            padding-bottom: 8px;
        }}
        .header h1 {{
            margin: 0 0 4px 0;
            font-size: 18px;
            color: #0f172a;
            font-weight: 700;
        }}
        .header .meta {{
            font-size: 11px;
            color: #64748b;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
            page-break-inside: auto;
        }}
        tr {{
            page-break-inside: avoid;
            page-break-after: auto;
        }}
        th {{
            background-color: #f1f5f9;
            color: #334155;
            font-weight: 600;
            text-align: left;
            padding: 7px 8px;
            border: 1px solid #cbd5e1;
            font-size: 11px;
        }}
        td {{
            padding: 6px 8px;
            border: 1px solid #e2e8f0;
            vertical-align: middle;
        }}
        tr:nth-child(even) {{
            background-color: #f8fafc;
        }}
        .footer {{
            margin-top: 16px;
            font-size: 10px;
            color: #94a3b8;
            display: flex;
            justify-content: space-between;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>DANH SÁCH TEMPLATE ĐỐI SOÁT — RECONHUB</h1>
        <div class="meta">{meta_line}</div>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 35px; text-align: center;">STT</th>
                <th style="width: 140px;">Mã template</th>
                <th style="width: 180px;">Tên template</th>
                <th style="width: 140px;">Nhận diện file</th>
                <th style="width: 75px; text-align: center;">Số trường</th>
                <th style="width: 150px;">Profiles</th>
                <th style="width: 65px; text-align: center;">Phiên bản</th>
                <th style="width: 80px;">Chủ sở hữu</th>
                <th style="width: 90px; text-align: center;">Trạng thái</th>
                <th style="width: 130px;">Run gần nhất</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
    <div class="footer">
        <span>ReconHub &middot; Hệ thống đối soát dữ liệu Excel và Oracle</span>
        <span>Tài liệu nội bộ &middot; In ngày {now_str}</span>
    </div>
</body>
</html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="load")
        pdf_bytes = page.pdf(
            format="A4",
            landscape=True,
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
        )
        browser.close()
        return pdf_bytes
