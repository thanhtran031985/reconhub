from __future__ import annotations

from typing import Any

import xlsxwriter

# Ngoại lệ hex duy nhất theo Spec 04 mục 10 và AGENTS.md
COLOR_DIFF_BG = "#FDECEC"
COLOR_HEADER_BG = "#F1F3F5"
COLOR_BORDER = "#D0D5DD"
COLOR_TITLE_BG = "#E9ECEF"


def get_export_formats(wb: xlsxwriter.Workbook) -> dict[str, Any]:
    """Tạo bộ định dạng chuẩn cho xuất file Excel qua XlsxWriter."""
    return {
        "title": wb.add_format({
            "bold": True,
            "font_size": 14,
            "font_name": "Segoe UI",
            "valign": "vcenter",
        }),
        "section_header": wb.add_format({
            "bold": True,
            "font_size": 11,
            "font_name": "Segoe UI",
            "bg_color": COLOR_TITLE_BG,
            "border": 1,
            "border_color": COLOR_BORDER,
            "valign": "vcenter",
        }),
        "table_header": wb.add_format({
            "bold": True,
            "font_size": 10,
            "font_name": "Segoe UI",
            "bg_color": COLOR_HEADER_BG,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
        }),
        "key_text": wb.add_format({
            "num_format": "@",
            "font_name": "Segoe UI",
            "font_size": 10,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "left",
            "valign": "vcenter",
        }),
        "text": wb.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "left",
            "valign": "vcenter",
        }),
        "text_center": wb.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "center",
            "valign": "vcenter",
        }),
        "number_integer": wb.add_format({
            "num_format": "#,##0",
            "font_name": "Segoe UI",
            "font_size": 10,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "right",
            "valign": "vcenter",
        }),
        "number_decimal": wb.add_format({
            "num_format": "#,##0.00",
            "font_name": "Segoe UI",
            "font_size": 10,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "right",
            "valign": "vcenter",
        }),
        "diff_number_integer": wb.add_format({
            "num_format": "#,##0",
            "font_name": "Segoe UI",
            "font_size": 10,
            "bg_color": COLOR_DIFF_BG,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "right",
            "valign": "vcenter",
        }),
        "diff_number_decimal": wb.add_format({
            "num_format": "#,##0.00",
            "font_name": "Segoe UI",
            "font_size": 10,
            "bg_color": COLOR_DIFF_BG,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "right",
            "valign": "vcenter",
        }),
        "diff_text": wb.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "bg_color": COLOR_DIFF_BG,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "left",
            "valign": "vcenter",
        }),
        "status_matched": wb.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "bold": True,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "center",
            "font_color": "#087F5B",
        }),
        "status_mismatch": wb.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "bold": True,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "center",
            "font_color": "#C92A2A",
        }),
        "status_missing": wb.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "bold": True,
            "border": 1,
            "border_color": COLOR_BORDER,
            "align": "center",
            "font_color": "#E67700",
        }),
    }
