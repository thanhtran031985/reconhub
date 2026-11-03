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


def generate_registration_workflow_diagram() -> str:
    """Sơ đồ quy trình đăng ký template 5 bước (flowchart LR)."""
    return (
        "flowchart LR\n"
        '    S1["1. File mẫu & Cấu trúc"] --> S2["2. Định nghĩa trường logic"]\n'
        '    S2 --> S3["3. Nguồn Oracle DB<br/>Bảng & Cột lọc"]\n'
        '    S3 --> S4["4. Profile đối soát<br/>Group by & Measures"]\n'
        '    S4 --> S5{"5. Dry-run đạt?"}\n'
        '    S5 -- "Đạt" --> A["Lưu & Kích hoạt"]\n'
        '    S5 -- "Chưa đạt" --> S2'
    )


def generate_three_layer_mapping_diagram(config: TemplateConfig) -> str:
    """Sơ đồ 3 lớp mapping: Excel -> Trường logic -> Oracle DB."""
    lines = ["flowchart LR"]
    sheet_name = config.file.sheet or "Excel"
    db_table = config.db_source.table or "Oracle DB"

    display_fields = config.fields[:10]

    lines.append(f'    subgraph EX["Excel · {sheet_name}"]')
    for i, f in enumerate(display_fields):
        lines.append(f'        E{i}["{f.excel or f.name}"]')
    lines.append("    end")

    lines.append('    subgraph LG["Trường logic"]')
    for i, f in enumerate(display_fields):
        lines.append(f'        L{i}(["{f.name}"])')
    lines.append("    end")

    lines.append(f'    subgraph DB["Oracle · {db_table}"]')
    for i, f in enumerate(display_fields):
        if f.db:
            lines.append(f'        D{i}["{f.db}"]')
    lines.append("    end")

    for i, f in enumerate(display_fields):
        lines.append(f"    E{i} --> L{i}")
        if f.db:
            lines.append(f"    D{i} --> L{i}")

    return "\n".join(lines)


def generate_time_filter_diagram(config: TemplateConfig) -> str:
    """Sơ đồ tham số thời gian áp dụng đồng thời cho DB và Excel."""
    flt_parts: list[str] = []
    for flt in config.db_source.filters:
        flt_parts.append(f"{flt.column} {flt.op} :{flt.param}")

    where_text = "<br/>AND ".join(flt_parts) if flt_parts else "INVOICE_DATE >= :p_from<br/>AND INVOICE_DATE <= :p_to"

    return (
        "flowchart TB\n"
        '    U["Tham số người dùng nhập:<br/>Từ ngày giờ (:p_from) → Đến ngày giờ (:p_to)"] --> V{"Kiểm tra hợp lệ?"}\n'
        '    V -- "Không" --> ERR["Báo lỗi, khóa nút Chạy"]\n'
        f'    V -- "Có" --> DBQ["Truy vấn Oracle DB có bind params:<br/>WHERE {where_text}"]\n'
        '    V -- "Có" --> XF["Lọc dữ liệu Excel:<br/>Chỉ giữ các dòng trong khoảng thời gian"]\n'
        '    XF --> OUT["Dòng ngoài khoảng: đếm và hiển thị thống kê"]'
    )


def generate_profile_match_diagram(config: TemplateConfig) -> str:
    """Sơ đồ gộp nhóm, ghép khóa và so khớp chỉ số của Profile."""
    prof = config.profiles[0] if config.profiles else None
    group_cols = ", ".join(prof.group_by) if prof and prof.group_by else "INVOICE_NO"
    measures_str = ", ".join(f"{m.name}({m.agg})" for m in prof.measures) if prof and prof.measures else "TOTAL_AMOUNT"

    return (
        "flowchart LR\n"
        f'    XE["Dữ liệu Excel hợp lệ"] --> GX["GROUP BY [{group_cols}]<br/>SUM({measures_str})"]\n'
        f'    QD["Dữ liệu Oracle DB nguồn"] --> GD["GROUP BY [{group_cols}]<br/>SUM({measures_str})"]\n'
        '    GX --> J{"Ghép khóa logic"}\n'
        "    GD --> J\n"
        '    J -- "Chỉ có ở Excel" --> M1["Thiếu trong DB"]\n'
        '    J -- "Chỉ có ở DB" --> M2["Thiếu trong Excel"]\n'
        '    J -- "Có ở cả hai" --> C{"So sai số cho phép"}\n'
        '    C -- "Trong ngưỡng" --> OK["Khớp (MATCHED)"]\n'
        '    C -- "Vượt ngưỡng" --> MM["Lệch giá trị (MISMATCH)"]'
    )


def generate_execution_sequence_diagram() -> str:
    """Sơ đồ tuần tự trình tự thực thi khi chạy đối soát (sequenceDiagram)."""
    return (
        "sequenceDiagram\n"
        "    actor U as Người dùng (Operator)\n"
        "    participant UI as ReconHub Web\n"
        "    participant W as Worker Engine\n"
        "    participant DB as Oracle Database (Thin)\n"
        "    U->>UI: Upload file Excel, chọn Profile & nhập khoảng ngày giờ\n"
        "    UI->>W: Gửi lệnh chạy vào hàng đợi (RECON_RUN_QUEUE)\n"
        "    W->>W: Đọc file Excel, lọc dòng header & chuẩn hóa theo trường logic\n"
        "    W->>W: Lọc dòng ngoài khoảng thời gian p_from..p_to\n"
        "    W->>DB: Thực thi truy vấn SQL gộp theo Profile có bind params\n"
        "    DB-->>W: Trả về kết quả DB đã tổng hợp nhóm\n"
        "    W->>W: Ghép khóa, so khớp giá trị & tính chỉ số chênh lệch\n"
        "    W->>UI: Lưu kết quả (DONE) vào DB ứng dụng & cập nhật giao diện\n"
        "    U->>UI: Xem kết quả, đánh dấu Đã kiểm tra & xử lý chênh lệch"
    )


def generate_all_diagrams(config: TemplateConfig) -> dict[str, str]:
    """Sinh 5 sơ đồ Mermaid cơ bản từ cấu hình Template."""
    return {
        "pipeline": generate_pipeline_diagram(config),
        "normalization": generate_fields_normalization_diagram(config),
        "db_query": generate_db_query_diagram(config),
        "profiles": generate_profiles_hierarchy_diagram(config),
        "control_total": generate_control_total_diagram(config),
    }


def generate_screen04_diagrams(config: TemplateConfig) -> dict[str, str]:
    """Sinh toàn bộ các sơ đồ Mermaid theo thiết kế Screen04."""
    base = generate_all_diagrams(config)
    base.update(
        {
            "workflow": generate_registration_workflow_diagram(),
            "three_layer": generate_three_layer_mapping_diagram(config),
            "time_filter": generate_time_filter_diagram(config),
            "profile_match": generate_profile_match_diagram(config),
            "sequence": generate_execution_sequence_diagram(),
        }
    )
    return base
