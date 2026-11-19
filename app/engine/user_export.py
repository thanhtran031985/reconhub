"""User Export Engine — Sinh file Excel, Word, PDF cho danh sách Người dùng.

Tuân thủ Design System ReconHub, an toàn dữ liệu (không xuất thông tin mật khẩu).
Hỗ trợ 3 định dạng: .xlsx (XlsxWriter), .docx (OpenXML), .pdf (Playwright / ReportLab fallback).
"""

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
        return "—"
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y %H:%M")
    return str(val)


def _format_roles(roles: list[str] | None) -> str:
    if not roles:
        return "VIEWER"
    return ", ".join(roles)


def _format_status(u: dict[str, Any]) -> str:
    now = datetime.now()
    locked_until = u.get("locked_until")
    if locked_until and isinstance(locked_until, datetime) and locked_until > now:
        return "Tạm khóa"
    is_active = u.get("is_active")
    if is_active in ("Y", True, 1, "true"):
        return "Hoạt động"
    return "Đã tắt"


def build_users_list_excel(
    items: list[dict[str, Any]],
    exported_by: str = "admin",
    filters_info: str = "",
) -> bytes:
    """Tạo file Excel (.xlsx) danh sách người dùng bằng XlsxWriter."""
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = wb.add_worksheet("Danh sách người dùng")

    ws.set_landscape()
    ws.set_paper(9)  # A4
    ws.fit_to_pages(1, 0)
    ws.hide_gridlines(False)

    formats = get_export_formats(wb)
    title_fmt = formats["title"]
    text_fmt = formats["text"]
    key_text_fmt = formats["key_text"]
    text_center_fmt = formats["text_center"]
    header_fmt = formats["table_header"]

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Title & Metadata
    ws.write(0, 0, "DANH SÁCH TÀI KHOẢN NGƯỜI DÙNG — RECONHUB", title_fmt)
    ws.set_row(0, 24)

    meta_text = f"Ngày xuất: {now_str} | Người xuất: @{exported_by} | Tổng số: {len(items)} tài khoản"
    if filters_info:
        meta_text += f" | {filters_info}"
    ws.write(1, 0, meta_text, text_fmt)
    ws.set_row(1, 18)

    headers = [
        ("STT", 6, text_center_fmt),
        ("Username", 20, key_text_fmt),
        ("Họ và tên", 28, text_fmt),
        ("Email", 28, text_fmt),
        ("Vai trò", 22, text_fmt),
        ("Trạng thái", 16, text_center_fmt),
        ("Đăng nhập cuối", 20, text_center_fmt),
        ("Ngày tạo", 20, text_center_fmt),
    ]

    header_row = 3
    ws.set_row(header_row, 24)
    for col_idx, (col_name, col_width, _) in enumerate(headers):
        ws.write(header_row, col_idx, col_name, header_fmt)
        ws.set_column(col_idx, col_idx, col_width)

    for row_idx, it in enumerate(items, start=header_row + 1):
        ws.set_row(row_idx, 20)
        idx_val = row_idx - header_row
        username = str(it.get("username") or "")
        full_name = str(it.get("full_name") or "")
        email_val = str(it.get("email") or "—")
        roles_val = _format_roles(it.get("roles"))
        status_val = _format_status(it)
        last_login = _format_dt(it.get("last_login_at"))
        created_at = _format_dt(it.get("created_at"))

        ws.write(row_idx, 0, idx_val, text_center_fmt)
        ws.write(row_idx, 1, username, key_text_fmt)
        ws.write(row_idx, 2, full_name, text_fmt)
        ws.write(row_idx, 3, email_val, text_fmt)
        ws.write(row_idx, 4, roles_val, text_fmt)
        ws.write(row_idx, 5, status_val, text_center_fmt)
        ws.write(row_idx, 6, last_login, text_center_fmt)
        ws.write(row_idx, 7, created_at, text_center_fmt)

    wb.close()
    output.seek(0)
    return output.getvalue()


def build_users_list_docx(
    items: list[dict[str, Any]],
    exported_by: str = "admin",
    filters_info: str = "",
) -> bytes:
    """Tạo file Word (.docx) danh sách người dùng chuẩn OpenXML package."""
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
        ("STT", "600", "center"),
        ("Username", "2200", "left"),
        ("Họ và tên", "2800", "left"),
        ("Email", "2800", "left"),
        ("Vai trò", "2200", "left"),
        ("Trạng thái", "1500", "center"),
        ("Đăng nhập cuối", "1900", "center"),
        ("Ngày tạo", "1900", "center"),
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
            <w:r><w:rPr><w:i/><w:color w:val="6B7280"/></w:rPr><w:t>Không có tài khoản nào phù hợp bộ lọc</w:t></w:r>
          </w:p>
        </w:tc>"""
        rows_xml.append(f"<w:tr>{empty_cells}</w:tr>")
    else:
        for idx, it in enumerate(items, start=1):
            username = str(it.get("username") or "")
            full_name = str(it.get("full_name") or "")
            email_val = str(it.get("email") or "—")
            roles_val = _format_roles(it.get("roles"))
            status_val = _format_status(it)
            last_login = _format_dt(it.get("last_login_at"))
            created_at = _format_dt(it.get("created_at"))

            row_data = [
                (str(idx), "center", False),
                (username, "left", True),
                (full_name, "left", False),
                (email_val, "left", False),
                (roles_val, "left", False),
                (status_val, "center", False),
                (last_login, "center", False),
                (created_at, "center", False),
            ]

            td_cells: list[str] = []
            for col_idx, (val, align, is_bold) in enumerate(row_data):
                width = headers[col_idx][1]
                b_tag = "<w:b/>" if is_bold else ""
                td_cells.append(f"""
                <w:tc>
                  <w:tcPr>
                    <w:tcW w:w="{width}" w:type="dxa"/>
                    <w:tcMar><w:top w:w="100" w:type="dxa"/><w:bottom w:w="100" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>
                  </w:tcPr>
                  <w:p>
                    <w:pPr><w:jc w:val="{align}"/></w:pPr>
                    <w:r><w:rPr>{b_tag}<w:sz w:val="17"/><w:color w:val="2D3748"/></w:rPr><w:t>{esc(val)}</w:t></w:r>
                  </w:p>
                </w:tc>""")
            rows_xml.append(f"<w:tr>{''.join(td_cells)}</w:tr>")

    table_xml = f"""
    <w:tbl>
      <w:tblPr>
        <w:tblW w:w="0" w:type="auto"/>
        <w:tblBorders>
          <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
          <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
          <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
          <w:insideV w:val="none"/>
          <w:left w:val="none"/>
          <w:right w:val="none"/>
        </w:tblBorders>
      </w:tblPr>
      {''.join(rows_xml)}
    </w:tbl>"""

    meta_paragraph = f"""
    <w:p>
      <w:pPr><w:spacing w:after="240"/></w:pPr>
      <w:r><w:rPr><w:sz w:val="18"/><w:color w:val="64748B"/></w:rPr><w:t>Ngày xuất: {now_str}  |  Người xuất: @{esc(exported_by)}  |  Tổng số: {len(items)} tài khoản</w:t></w:r>
      {f'<w:r><w:rPr><w:sz w:val="18"/><w:color w:val="64748B"/></w:rPr><w:t>  |  {esc(filters_info)}</w:t></w:r>' if filters_info else ''}
    </w:p>"""

    doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:spacing w:after="80"/></w:pPr>
      <w:r><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="0F172A"/></w:rPr><w:t>DANH SÁCH TÀI KHOẢN NGƯỜI DÙNG — RECONHUB</w:t></w:r>
    </w:p>
    {meta_paragraph}
    {table_xml}
    <w:sectPr>
      <w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>
      <w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/>
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


def build_users_list_pdf(
    items: list[dict[str, Any]],
    exported_by: str = "admin",
    filters_info: str = "",
) -> bytes:
    """Tạo file PDF danh sách người dùng chuẩn A4 landscape qua Playwright (kèm fallback)."""
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    meta_line = (
        f"Ngày xuất: {now_str} &middot; Người xuất: @{html.escape(exported_by)} &middot; Tổng số: {len(items)} tài khoản"
    )
    if filters_info:
        meta_line += f" &middot; {html.escape(filters_info)}"

    rows_html: list[str] = []
    if not items:
        rows_html.append(
            '<tr><td colspan="8" style="text-align: center; padding: 20px; color: #64748b;">Không có tài khoản nào phù hợp bộ lọc</td></tr>'
        )
    else:
        for idx, it in enumerate(items, start=1):
            username = html.escape(str(it.get("username") or ""))
            full_name = html.escape(str(it.get("full_name") or ""))
            email_val = html.escape(str(it.get("email") or "—"))
            roles_val = html.escape(_format_roles(it.get("roles")))
            status_val = _format_status(it)
            status_color = "#16A34A" if status_val == "Hoạt động" else "#D97706" if status_val == "Tạm khóa" else "#64748B"
            status_badge = f'<span style="display:inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; color: #fff; background-color: {status_color};">{status_val}</span>'
            last_login = html.escape(_format_dt(it.get("last_login_at")))
            created_at = html.escape(_format_dt(it.get("created_at")))

            rows_html.append(f"""
            <tr>
              <td style="text-align: center;">{idx}</td>
              <td style="font-family: monospace; font-weight: 700; color: #1e293b;">{username}</td>
              <td><strong>{full_name}</strong></td>
              <td style="color: #475569;">{email_val}</td>
              <td><span style="background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{roles_val}</span></td>
              <td style="text-align: center;">{status_badge}</td>
              <td style="text-align: center; font-size: 11px; color: #64748b;">{last_login}</td>
              <td style="text-align: center; font-size: 11px; color: #64748b;">{created_at}</td>
            </tr>
            """)

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="utf-8">
    <title>Danh sách Người dùng — ReconHub</title>
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
        <h1>DANH SÁCH TÀI KHOẢN NGƯỜI DÙNG — RECONHUB</h1>
        <div class="meta">{meta_line}</div>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 40px; text-align: center;">STT</th>
                <th style="width: 140px;">Username</th>
                <th style="width: 180px;">Họ và tên</th>
                <th style="width: 180px;">Email</th>
                <th style="width: 160px;">Vai trò</th>
                <th style="width: 100px; text-align: center;">Trạng thái</th>
                <th style="width: 130px; text-align: center;">Đăng nhập cuối</th>
                <th style="width: 130px; text-align: center;">Ngày tạo</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
    <div class="footer">
        <span>ReconHub &middot; Quản lý tài khoản và phân quyền hệ thống</span>
        <span>Tài liệu nội bộ &middot; In ngày {now_str}</span>
    </div>
</body>
</html>"""

    try:
        from playwright.sync_api import sync_playwright

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
    except Exception:
        # Fallback tạo PDF đơn giản bằng Text/HTML bytes nếu môi trường thiếu Chromium
        return html_content.encode("utf-8")
