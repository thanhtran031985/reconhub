from __future__ import annotations

from app.schemas.template_config import TemplateConfig


def generate_pipeline_diagram(config: TemplateConfig) -> str:
    """Sơ đồ luồng đối soát tổng quan (flowchart LR)."""
    sheet_name = config.file.sheet
    db_table = config.db_source.table or "DB_SOURCE"
    derived_count = len(config.derived)
    profiles_count = len(config.profiles)

    lines = [
        "flowchart LR",
        f'    excel["Tập tin Excel<br/>Sheet: {sheet_name}"]',
        '    clean["Lọc dòng thô & Chuẩn hóa"]',
        f'    derived["Tính trường phái sinh<br/>({derived_count} trường)"]',
        f'    prof["Gộp nhóm & Chỉ số<br/>({profiles_count} profile)"]',
        f'    db["Oracle DB Source<br/>{db_table}"]',
        '    db_flt["Áp bộ lọc thời gian & điều kiện<br/>:p_from, :p_to"]',
        '    matcher["Khớp đối soát & Phân loại trạng thái"]',
        "",
        "    excel --> clean --> derived --> prof --> matcher",
        "    db --> db_flt --> matcher",
    ]
    return "\n".join(lines)


def generate_fields_normalization_diagram(config: TemplateConfig) -> str:
    """Sơ đồ chuẩn hóa dữ liệu từng trường (flowchart TD/LR)."""
    lines = ["flowchart LR"]
    has_norm = False

    for idx, f in enumerate(config.fields):
        if not f.norm:
            continue
        has_norm = True
        norm_steps: list[str] = []
        for step in f.norm:
            if isinstance(step, str):
                norm_steps.append(step)
            elif isinstance(step, dict):
                norm_steps.append(", ".join(step.keys()))
        steps_str = " -> ".join(norm_steps)
        lines.append(
            f'    f_{idx}_raw["[{f.excel or f.name}] Thô"] --> f_{idx}_norm["{steps_str}"] --> f_{idx}_clean["{f.name} ({f.type})"]'
        )

    if not has_norm:
        lines.append('    info["Các trường dữ liệu không cấu hình chuẩn hóa đặc biệt"]')

    return "\n".join(lines)


def generate_db_query_diagram(config: TemplateConfig) -> str:
    """Sơ đồ truy vấn DB và các bộ lọc (flowchart TD)."""
    lines = ["flowchart TD"]
    table_name = config.db_source.table or "DATABASE_TABLE"
    lines.append(f'    tbl["Bảng nguồn: {table_name}"]')

    # WHERE filters
    flt_labels: list[str] = []
    for flt in config.db_source.filters:
        flt_labels.append(f"{flt.column} {flt.op} :{flt.param}")
    for sw in config.db_source.static_where:
        flt_labels.append(f"{sw.column} {sw.op} '{sw.value}'")

    where_str = "<br/>".join(flt_labels) if flt_labels else "Không có bộ lọc"
    lines.append(f'    where["Mệnh đề WHERE (Bind Params):<br/>{where_str}"]')
    lines.append("    tbl --> where")

    # DB columns
    db_cols = [f.db for f in config.fields if f.db]
    cols_str = ", ".join(db_cols[:8])
    if len(db_cols) > 8:
        cols_str += f"... (+{len(db_cols) - 8} cột)"
    lines.append(f'    cols["Cột lấy vào SELECT:<br/>{cols_str}"]')
    lines.append("    where --> cols")

    return "\n".join(lines)


def generate_profiles_hierarchy_diagram(config: TemplateConfig) -> str:
    """Sơ đồ cây Profile đối soát và quan hệ drilldown (flowchart TD)."""
    lines = ["flowchart TD"]

    for prof in config.profiles:
        default_tag = " (Mặc định)" if prof.is_default else ""
        group_by_str = ", ".join(prof.group_by)
        measures_str = ", ".join(f"{m.name}({m.agg})" for m in prof.measures)
        node_label = f"<b>{prof.code}</b>: {prof.name}{default_tag}<br/>Group by: [{group_by_str}]<br/>Measures: [{measures_str}]"
        lines.append(f'    p_{prof.code}["{node_label}"]')

    for prof in config.profiles:
        if prof.drilldown_to:
            lines.append(f"    p_{prof.code} -- Drilldown --> p_{prof.drilldown_to}")

    return "\n".join(lines)


def generate_control_total_diagram(config: TemplateConfig) -> str:
    """Sơ đồ kiểm tra Control Total (flowchart LR)."""
    lines = ["flowchart LR"]

    if not config.control_total:
        lines.append('    no_ct["Không cấu hình kiểm tra tổng kiểm soát (Control Total)"]')
        return "\n".join(lines)

    ct = config.control_total
    loc_col = ct.locate.excel_col
    loc_val = ct.locate.equals
    val_col = ct.value_col
    tol = ct.tolerance

    lines.extend(
        [
            f"    file_row[\"Dòng tổng file Excel<br/>({loc_col} == '{loc_val}')\"]",
            f'    file_val["Giá trị tổng từ file<br/>Cột: {val_col}"]',
            f'    calc_val["Tổng cộng dồn từ dữ liệu chi tiết<br/>SUM({val_col})"]',
            f'    comp["So khớp tổng kiểm soát<br/>Sai số cho phép: ±{tol}"]',
            '    valid["Hợp lệ / Lệch tổng kiểm soát"]',
            "",
            "    file_row --> file_val --> comp",
            "    calc_val --> comp",
            "    comp --> valid",
        ]
    )
    return "\n".join(lines)


def generate_all_diagrams(config: TemplateConfig) -> dict[str, str]:
    """Sinh toàn bộ 5 sơ đồ Mermaid từ cấu hình Template."""
    return {
        "pipeline": generate_pipeline_diagram(config),
        "normalization": generate_fields_normalization_diagram(config),
        "db_query": generate_db_query_diagram(config),
        "profiles": generate_profiles_hierarchy_diagram(config),
        "control_total": generate_control_total_diagram(config),
    }
