"""Schema Inspector — đọc schema thật của ReconHub, sinh manifest/history.

Tool thuần (không phải service người dùng): không dùng ``ctx``, không dùng
decorator ``@service``. Nguồn sự thật là ``app/db/metadata.py`` (model
SQLAlchemy Core) + các file migration Alembic; inspector chỉ đọc database
SQLite của app (``RECON_DB_URL``), không đọc Oracle data source nghiệp vụ.

Chạy: ``uv run poe schema-introspect`` (xem ``scripts/schema_introspect.py``).
"""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, UniqueConstraint, inspect
from sqlalchemy.dialects import sqlite as sqlite_dialect

from app.db.metadata import metadata as app_metadata

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"
MODEL_SOURCE = "app/db/metadata.py"

_GENERATOR = "schema-introspect"

DOMAIN_LABELS: dict[str, str] = {
    "core": "Core",
    "recon": "Đối soát",
    "report": "Báo cáo",
    "admin": "Quản trị",
    "other": "Khác",
}

# Quy tắc "lai" đã chốt (task.md mục Domain Mapping): tiền tố + ngoại lệ.
_CORE_EXACT = {
    "RECON_LOGIN_LOG",
    "RECON_AUDIT_LOG",
    "RECON_APP_SETTING",
    "RECON_METADATA_MIGRATION",
}
_CORE_PREFIXES = ("RECON_USER", "RECON_ROLE", "RECON_MENU")

TABLE_DESCRIPTIONS: dict[str, str] = {
    "RECON_USER": "Người dùng đăng nhập",
    "RECON_USER_ROLE": "Vai trò của người dùng",
    "RECON_MENU_GROUP": "Nhóm menu",
    "RECON_MENU": "Menu của ứng dụng",
    "RECON_ROLE": "Vai trò",
    "RECON_ROLE_MENU": "Quyền menu của vai trò",
    "RECON_LOGIN_LOG": "Lịch sử đăng nhập",
    "RECON_AUDIT_LOG": "Nhật ký kiểm tra (audit)",
    "RECON_APP_SETTING": "Cài đặt ứng dụng",
    "RECON_DATA_SOURCE": "Nguồn dữ liệu (Data Source)",
    "RECON_TEMPLATE": "Template đối soát",
    "RECON_TEMPLATE_VERSION": "Phiên bản template",
    "RECON_FILE": "File đã upload",
    "RECON_EXCEL_LOAD": "Lần nạp dữ liệu Excel",
    "RECON_EXCEL_ROW": "Dòng dữ liệu Excel đã nạp",
    "RECON_RUN": "Lần chạy đối soát",
    "RECON_RUN_QUEUE": "Hàng đợi chạy",
    "RECON_RUN_SUMMARY": "Tóm tắt kết quả lần chạy",
    "RECON_BATCH_DEF": "Bộ đối soát (định nghĩa)",
    "RECON_BATCH_DEF_ITEM": "Mục trong bộ đối soát",
    "RECON_BATCH_RUN": "Lần chạy bộ đối soát",
    "RECON_BATCH_RUN_ITEM": "Mục của lần chạy bộ",
    "RECON_BATCH_RUN_FILE": "File của lần chạy bộ",
    "RECON_RESULT_ROW": "Dòng kết quả đối soát",
    "RECON_RESULT_DIFF": "Chênh lệch theo chỉ số",
    "RECON_INVALID_ROW": "Dòng Excel không hợp lệ",
    "RECON_ISSUE": "Chênh lệch cần xử lý (issue)",
    "RECON_ISSUE_REASON": "Lý do chênh lệch",
    "RECON_LOOKUP_TYPE": "Loại danh mục dùng chung",
    "RECON_LOOKUP_CODE": "Mã danh mục dùng chung",
    "RECON_PURGE_LOG": "Lịch sử xóa dữ liệu tạm",
    "RECON_METADATA_MIGRATION": "Lần chuyển metadata",
    "RECON_REPORT": "Báo cáo",
    "RECON_REPORT_TEMPLATE": "Template báo cáo",
    "RECON_RPT_TPL_VER": "Phiên bản template báo cáo",
    "RECON_RPT_PARAM": "Tham số báo cáo",
    "RECON_RPT_PARAM_LOV": "Danh sách giá trị tham số",
    "RECON_RPT_COLUMN": "Cột báo cáo",
    "RECON_REPORT_RUN": "Lần chạy báo cáo",
    "RECON_RPT_EXPORT": "Lần xuất báo cáo",
    "RECON_RPT_FAVORITE": "Báo cáo yêu thích",
    "RECON_RPT_PRESET": "Preset tham số báo cáo",
    "RECON_RPT_LOV_CACHE": "Cache danh sách giá trị",
}

_SQLITE_DIALECT = sqlite_dialect.dialect()


def domain_for_table(name: str) -> tuple[str, str]:
    """Trả (code, label) phân hệ của bảng theo quy tắc đã chốt."""
    if name.startswith("RECON_RPT_") or name.startswith("RECON_REPORT"):
        code = "report"
    elif name.startswith("RECON_BATCH_"):
        code = "recon"
    elif name.startswith("RECON_LOOKUP_") or name == "RECON_DATA_SOURCE":
        code = "admin"
    elif name in _CORE_EXACT or name.startswith(_CORE_PREFIXES):
        code = "core"
    elif name.startswith("RECON_"):
        code = "recon"
    else:
        code = "other"
    return code, DOMAIN_LABELS[code]


def _render_model_type(col_type: Any) -> str:
    """Render kiểu cột bằng SQLite dialect compiler (vd String(60) -> VARCHAR(60))."""
    return str(col_type.compile(dialect=_SQLITE_DIALECT))


def _column_default(column: Any) -> str | None:
    """str của default nếu là literal, None nếu không có/không render an toàn."""
    default = column.default
    if default is not None:
        arg = default.arg
        if isinstance(arg, (str, int, float, bool)):
            return str(arg)
        return None
    server_default = column.server_default
    if server_default is not None and isinstance(server_default.arg, str):
        return server_default.arg
    return None


def _model_table(table: Any) -> dict[str, Any]:
    """Trích một bảng từ model SQLAlchemy Core về shape chuẩn."""
    single_unique = {
        next(iter(uc.columns)).name
        for uc in table.constraints
        if isinstance(uc, UniqueConstraint) and len(uc.columns) == 1
    }
    pk_columns = [c.name for c in table.primary_key.columns]
    columns: list[dict[str, Any]] = []
    foreign_keys: list[dict[str, Any]] = []
    for col in table.columns:
        fks = list(col.foreign_keys)
        fk = fks[0] if fks else None
        if fk is not None:
            foreign_keys.append(
                {
                    "column": col.name,
                    "references_table": fk.column.table.name,
                    "references_column": fk.column.name,
                    "constraint_name": fk.constraint.name if fk.constraint is not None else None,
                    "on_delete": fk.ondelete,
                }
            )
        columns.append(
            {
                "name": col.name,
                "type": _render_model_type(col.type),
                "nullable": bool(col.nullable),
                "primary_key": col.name in pk_columns,
                "foreign_key": f"{fk.column.table.name}.{fk.column.name}" if fk is not None else None,
                "unique": col.name in single_unique,
                "default": _column_default(col),
            }
        )
    return {
        "name": table.name,
        "columns": columns,
        "primary_key": pk_columns,
        "foreign_keys": foreign_keys,
        "unique_constraints": [
            {"name": uc.name, "columns": [c.name for c in uc.columns]}
            for uc in table.constraints
            if isinstance(uc, UniqueConstraint)
        ],
        "indexes": [
            {"name": ix.name, "columns": [c.name for c in ix.columns], "unique": bool(ix.unique)}
            for ix in table.indexes
        ],
    }


def extract_model_schema() -> list[dict[str, Any]]:
    """Trích toàn bộ schema từ ``app/db/metadata.py``, bảng sắp theo tên."""
    return [_model_table(app_metadata.tables[name]) for name in sorted(app_metadata.tables)]


def inspect_live_db(engine: Engine) -> list[dict[str, Any]]:
    """Trích schema từ database SQLite thật qua SQLAlchemy inspector.

    Shape chuẩn hoá giống :func:`extract_model_schema` để so sánh được;
    tên constraint FK không so được vì SQLite trả None (xem schema_drift).
    """
    insp = inspect(engine)
    tables: list[dict[str, Any]] = []
    for name in sorted(insp.get_table_names()):
        pk_columns = list(insp.get_pk_constraint(name).get("constrained_columns") or [])
        fk_by_column: dict[str, tuple[str, str]] = {}
        foreign_keys: list[dict[str, Any]] = []
        for fk in insp.get_foreign_keys(name):
            options = fk.get("options") or {}
            for constrained, referred in zip(fk["constrained_columns"], fk["referred_columns"], strict=True):
                fk_by_column[constrained] = (fk["referred_table"], referred)
                foreign_keys.append(
                    {
                        "column": constrained,
                        "references_table": fk["referred_table"],
                        "references_column": referred,
                        "constraint_name": fk.get("name"),
                        "on_delete": options.get("ondelete"),
                    }
                )
        single_unique = {
            uq["column_names"][0] for uq in insp.get_unique_constraints(name) if len(uq["column_names"]) == 1
        }
        columns: list[dict[str, Any]] = []
        for col in insp.get_columns(name):
            ref = fk_by_column.get(col["name"])
            default = col.get("default")
            columns.append(
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": bool(col["nullable"]),
                    "primary_key": col["name"] in pk_columns,
                    "foreign_key": f"{ref[0]}.{ref[1]}" if ref is not None else None,
                    "unique": col["name"] in single_unique,
                    "default": str(default) if default is not None else None,
                }
            )
        tables.append(
            {
                "name": name,
                "columns": columns,
                "primary_key": pk_columns,
                "foreign_keys": foreign_keys,
                "unique_constraints": [
                    {"name": uq.get("name"), "columns": list(uq["column_names"])}
                    for uq in insp.get_unique_constraints(name)
                ],
                "indexes": [
                    {"name": ix["name"], "columns": list(ix["column_names"]), "unique": bool(ix["unique"])}
                    for ix in insp.get_indexes(name)
                ],
            }
        )
    return tables


# --- Parse migration -----------------------------------------------------

_SA_TYPE_MAP = {
    "String": "VARCHAR",
    "Integer": "INTEGER",
    "BigInteger": "BIGINT",
    "DateTime": "DATETIME",
    "Text": "TEXT",
    "Float": "FLOAT",
    "Numeric": "NUMERIC",
    "Boolean": "BOOLEAN",
}


def _render_sa_type(column_text: str) -> str:
    """Render kiểu từ đoạn ``sa.Column(...)`` trong file migration."""
    if "JsonText" in column_text:
        return "TEXT"
    if "DecimalText" in column_text:
        return "VARCHAR(60)"
    variant = re.search(r"with_variant\(sa\.(\w+)", column_text)
    if variant is not None:
        base = _SA_TYPE_MAP.get(variant.group(1), variant.group(1).upper())
        return base
    match = None
    for candidate in re.finditer(r"sa\.(\w+)", column_text):
        if candidate.group(1) == "Column":
            continue
        match = candidate
        break
    if match is None:
        return "UNKNOWN"
    type_name = match.group(1)
    base = _SA_TYPE_MAP.get(type_name, type_name.upper())
    args_match = re.match(r"\s*\(([^)]*)\)", column_text[match.end() :])
    args = (args_match.group(1) if args_match else "").strip()
    if type_name in ("String", "Numeric") and args:
        return f"{base}({args})"
    return base


def _column_nullable(column_text: str) -> bool:
    match = re.search(r"nullable\s*=\s*(True|False)", column_text)
    return match.group(1) == "True" if match else True


def _matching_paren_end(text: str, start: int) -> int:
    """Vị trí đóng ngoặc tương ứng với '(' tại ``start``."""
    depth = 0
    in_str: str | None = None
    prev = ""
    for i in range(start, len(text)):
        ch = text[i]
        if in_str is not None:
            if ch == in_str and prev != "\\":
                in_str = None
        elif ch in ("'", '"'):
            in_str = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        prev = ch
    return len(text) - 1


def _parse_upgrade_events(body: str, revision: str, timestamp: str | None) -> list[dict[str, Any]]:
    """Parse các statement tạo bảng/thêm-xóa-sửa cột trong thân ``upgrade()``.

    Chỉ parse ``upgrade()`` (không parse ``downgrade()``) để event không bị
    đảo ngược. ``batch_op.*`` lấy bảng từ ``with op.batch_alter_table(...)``
    gần nhất phía trên.
    """
    events: list[dict[str, Any]] = []
    batch_table: str | None = None
    batch_indent: int | None = None
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if batch_table is not None and stripped and batch_indent is not None and indent <= batch_indent:
            batch_table = None
            batch_indent = None
        batch_match = re.match(r"with op\.batch_alter_table\(\"([^\"]+)\"", stripped)
        if batch_match is not None:
            batch_table = batch_match.group(1)
            batch_indent = indent
            i += 1
            continue
        call = re.search(r"(op|batch_op)\.(create_table|add_column|drop_column|alter_column)\(", line)
        if call is None:
            i += 1
            continue
        # Gom đủ statement (cân bằng ngoặc) rồi xử lý.
        start = line.index(call.group(0)) + len(call.group(0)) - 1
        stmt_lines = [line]
        depth_text = line[start:]
        depth = depth_text.count("(") - depth_text.count(")")
        j = i
        while depth > 0 and j + 1 < len(lines):
            j += 1
            stmt_lines.append(lines[j])
            depth += lines[j].count("(") - lines[j].count(")")
        stmt = "\n".join(stmt_lines)
        kind = call.group(2)
        receiver = call.group(1)

        def _event(entity: str, change_type: str, before: Any, after: Any) -> dict[str, Any]:
            return {
                "timestamp": timestamp,
                "task_id": None,
                "migration_id": revision,
                "entity": entity,
                "change_type": change_type,
                "before": before,
                "after": after,
            }

        if kind == "create_table":
            name_match = re.search(r'create_table\(\s*"([^"]+)"', stmt)
            if name_match is not None:
                events.append(_event(name_match.group(1), "TABLE_CREATED", None, "TABLE"))
        elif kind in ("add_column", "alter_column", "drop_column"):
            if receiver == "op":
                table_match = re.search(rf'{kind}\(\s*"([^"]+)"', stmt)
                table = table_match.group(1) if table_match else None
            else:
                table = batch_table
            col_match = re.search(r'sa\.Column\(\s*"([^"]+)"', stmt)
            quoted = re.findall(r'"([^"]+)"', stmt)
            if kind == "add_column" and table is not None and col_match is not None:
                col_text = stmt[stmt.index("sa.Column(") :]
                col_end = _matching_paren_end(col_text, col_text.index("("))
                col_inner = col_text[: col_end + 1]
                events.append(
                    _event(
                        f"{table}.{col_match.group(1)}",
                        "COLUMN_ADDED",
                        None,
                        f"{_render_sa_type(col_inner)}, nullable={_column_nullable(col_inner)}",
                    )
                )
            elif kind == "drop_column" and table is not None and len(quoted) >= 1:
                col_name = quoted[-1] if receiver == "op" else quoted[0]
                events.append(_event(f"{table}.{col_name}", "COLUMN_REMOVED", col_name, None))
            elif kind == "alter_column" and table is not None and len(quoted) >= 1:
                col_name = quoted[-1] if receiver == "op" else quoted[0]
                type_match = re.search(r"type_\s*=\s*sa\.(\w+)\s*(?:\(([^)]*)\))?", stmt)
                nullable_match = re.search(r"nullable\s*=\s*(True|False)", stmt)
                if type_match is not None:
                    base = _SA_TYPE_MAP.get(type_match.group(1), type_match.group(1).upper())
                    args = (type_match.group(2) or "").strip()
                    type_str = f"{base}({args})" if args and type_match.group(1) in ("String", "Numeric") else base
                    after = f"{type_str}, nullable={nullable_match.group(1)}" if nullable_match else type_str
                elif nullable_match is not None:
                    after = f"nullable={nullable_match.group(1)}"
                else:
                    after = "ALTERED"
                events.append(_event(f"{table}.{col_name}", "COLUMN_CHANGED", None, after))
        i = j + 1
    return events


def _parse_migration_file(path: Path) -> dict[str, Any]:
    """Parse một file migration: revision, timestamp, events của upgrade()."""
    text = path.read_text(encoding="utf-8")
    revision_match = re.search(r"^revision:\s*str\s*=\s*\"([^\"]+)\"", text, re.MULTILINE)
    revision = revision_match.group(1) if revision_match else path.stem
    down_match = re.search(r"^down_revision[^=]*=\s*\"([^\"]+)\"", text, re.MULTILINE)
    down_revision = down_match.group(1) if down_match else None
    created_match = re.search(r"Create Date:\s*([0-9\-: .]+)", text)
    timestamp: str | None = None
    if created_match is not None:
        raw = created_match.group(1).strip()
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            timestamp = parsed.isoformat()
    upgrade_match = re.search(r"^def upgrade\(.*$", text, re.MULTILINE)
    events: list[dict[str, Any]] = []
    if upgrade_match is not None:
        body = text[upgrade_match.end() :]
        downgrade_match = re.search(r"^def downgrade\(.*$", body, re.MULTILINE)
        if downgrade_match is not None:
            body = body[: downgrade_match.start()]
        events = _parse_upgrade_events(body, revision, timestamp)
    return {
        "revision": revision,
        "down_revision": down_revision,
        "created_at": timestamp,
        "events": events,
        "path": path,
    }


def _migration_files(migrations_dir: Path | None = None) -> list[dict[str, Any]]:
    directory = migrations_dir or MIGRATIONS_DIR
    files = sorted(directory.glob("*.py"))
    return [_parse_migration_file(p) for p in files]


def get_head_revision(migrations_dir: Path | None = None) -> str | None:
    """Revision head của Alembic (revision không bị revision khác trỏ tới)."""
    parsed = _migration_files(migrations_dir)
    revisions = {m["revision"] for m in parsed}
    downs = {m["down_revision"] for m in parsed if m["down_revision"]}
    heads = revisions - downs
    if not heads:
        return None
    if len(heads) == 1:
        return str(next(iter(heads)))
    # Nhiều head (nhánh rẽ): lấy head của file mới nhất theo tên file.
    for m in reversed(parsed):
        if m["revision"] in heads:
            return str(m["revision"])
    return None


def table_migration_map(migrations_dir: Path | None = None) -> dict[str, str]:
    """Map tên bảng -> revision tạo bảng đó (suy từ op.create_table)."""
    mapping: dict[str, str] = {}
    for m in _migration_files(migrations_dir):
        for event in m["events"]:
            if event["change_type"] == "TABLE_CREATED":
                mapping[str(event["entity"])] = str(m["revision"])
    return mapping


def seed_history_from_migrations(migrations_dir: Path | None = None) -> list[dict[str, Any]]:
    """Sinh history ban đầu bằng cách parse toàn bộ file migration.

    Bắt buộc sinh TABLE_CREATED cho đủ 43 bảng. Chỉ parse ``upgrade()``.
    """
    events: list[dict[str, Any]] = []
    for m in _migration_files(migrations_dir):
        events.extend(m["events"])
    return events


# --- Manifest / history --------------------------------------------------


def build_manifest(migrations_dir: Path | None = None) -> dict[str, Any]:
    """Build manifest từ model + migration (không đọc DB thật)."""
    migration_by_table = table_migration_map(migrations_dir)
    tables: list[dict[str, Any]] = []
    warnings: list[str] = []
    for table in extract_model_schema():
        code, label = domain_for_table(table["name"])
        if code == "other":
            warnings.append(f"Bảng {table['name']} không khớp quy tắc domain nào (domain Khác).")
        tables.append(
            {
                "name": table["name"],
                "domain": code,
                "domain_label": label,
                "description": TABLE_DESCRIPTIONS.get(table["name"], ""),
                "columns": table["columns"],
                "primary_key": table["primary_key"],
                "foreign_keys": table["foreign_keys"],
                "unique_constraints": table["unique_constraints"],
                "indexes": table["indexes"],
                "source": {
                    "model": MODEL_SOURCE,
                    "migration": migration_by_table.get(table["name"]),
                },
            }
        )
    return {
        "generated": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": _GENERATOR,
        "database": "sqlite",
        "schema": "main",
        "version": get_head_revision(migrations_dir),
        "tables": tables,
        "warnings": warnings,
    }


def normalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Bỏ trường volatile (generated_at) để so sánh manifest 2 lần chạy."""
    normalized = copy.deepcopy(manifest)
    normalized.pop("generated_at", None)
    return normalized


def write_manifest(manifest: dict[str, Any] | list[dict[str, Any]], path: Path | str) -> None:
    """Ghi manifest/history ra JSON (indent 2, UTF-8, newline cuối file)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _column_after(column: dict[str, Any]) -> str:
    return f"{column['type']}, nullable={column['nullable']}"


def _fk_signature(foreign_keys: list[dict[str, Any]]) -> str | None:
    if not foreign_keys:
        return None
    parts = sorted(f"{fk['column']}->{fk['references_table']}.{fk['references_column']}" for fk in foreign_keys)
    return "; ".join(parts)


def _index_signature(indexes: list[dict[str, Any]]) -> str | None:
    if not indexes:
        return None
    parts = sorted(f"{ix['name']}({','.join(ix['columns'])}){' UNIQUE' if ix['unique'] else ''}" for ix in indexes)
    return "; ".join(parts)


def _constraint_signature(unique_constraints: list[dict[str, Any]]) -> str | None:
    if not unique_constraints:
        return None
    parts = sorted(",".join(uc["columns"]) for uc in unique_constraints)
    return "; ".join(parts)


def append_history_events(
    prev_manifest: dict[str, Any], new_manifest: dict[str, Any], migration_id: str | None
) -> list[dict[str, Any]]:
    """Diff 2 manifest -> event history mới. Diff rỗng -> không event mới."""
    now = datetime.now(timezone.utc).isoformat()
    events: list[dict[str, Any]] = []

    def _event(entity: str, change_type: str, before: Any, after: Any) -> dict[str, Any]:
        return {
            "timestamp": now,
            "task_id": None,
            "migration_id": migration_id,
            "entity": entity,
            "change_type": change_type,
            "before": before,
            "after": after,
        }

    prev_tables = {t["name"]: t for t in prev_manifest.get("tables", [])}
    new_tables = {t["name"]: t for t in new_manifest.get("tables", [])}
    for name in sorted(set(prev_tables) - set(new_tables)):
        events.append(_event(name, "TABLE_DROPPED", "TABLE", None))
    for name in sorted(set(new_tables) - set(prev_tables)):
        events.append(_event(name, "TABLE_CREATED", None, "TABLE"))
    for name in sorted(set(prev_tables) & set(new_tables)):
        prev_table = prev_tables[name]
        new_table = new_tables[name]
        prev_cols = {c["name"]: c for c in prev_table["columns"]}
        new_cols = {c["name"]: c for c in new_table["columns"]}
        for col_name in sorted(set(prev_cols) - set(new_cols)):
            events.append(_event(f"{name}.{col_name}", "COLUMN_REMOVED", col_name, None))
        for col_name in sorted(set(new_cols) - set(prev_cols)):
            events.append(_event(f"{name}.{col_name}", "COLUMN_ADDED", None, _column_after(new_cols[col_name])))
        for col_name in sorted(set(prev_cols) & set(new_cols)):
            old = prev_cols[col_name]
            new_col = new_cols[col_name]
            if old["type"] != new_col["type"] or old["nullable"] != new_col["nullable"]:
                events.append(
                    _event(
                        f"{name}.{col_name}",
                        "COLUMN_CHANGED",
                        _column_after(old),
                        _column_after(new_col),
                    )
                )
        if list(prev_table["primary_key"]) != list(new_table["primary_key"]):
            events.append(
                _event(
                    name,
                    "PK_CHANGED",
                    ", ".join(prev_table["primary_key"]) or None,
                    ", ".join(new_table["primary_key"]) or None,
                )
            )
        if _fk_signature(prev_table["foreign_keys"]) != _fk_signature(new_table["foreign_keys"]):
            events.append(
                _event(
                    name,
                    "FK_CHANGED",
                    _fk_signature(prev_table["foreign_keys"]),
                    _fk_signature(new_table["foreign_keys"]),
                )
            )
        if _index_signature(prev_table["indexes"]) != _index_signature(new_table["indexes"]):
            events.append(
                _event(
                    name,
                    "INDEX_CHANGED",
                    _index_signature(prev_table["indexes"]),
                    _index_signature(new_table["indexes"]),
                )
            )
        if _constraint_signature(prev_table["unique_constraints"]) != _constraint_signature(
            new_table["unique_constraints"]
        ):
            events.append(
                _event(
                    name,
                    "CONSTRAINT_CHANGED",
                    _constraint_signature(prev_table["unique_constraints"]),
                    _constraint_signature(new_table["unique_constraints"]),
                )
            )
    return events


def generate_all(out_dir: Path | str, db_url: str | None = None) -> dict[str, Any]:
    """Build manifest từ model, seed/append history, ghi 2 artifact JSON.

    ``db_url`` giữ chỗ cho bước drift/live-check sau này; manifest hiện tại
    chỉ suy từ model + migration nên không cần DB thật. Để tránh churn git:
    manifest mới normalize-giống file đã có thì KHÔNG ghi lại (giữ nguyên
    ``generated_at`` cũ); history chỉ append event thật mới.
    """
    _ = db_url
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    manifest_path = out / "schema-manifest.json"
    history_path = out / "schema-history.json"

    prev_manifest: dict[str, Any] | None = None
    if manifest_path.exists():
        prev_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_changed = prev_manifest is None or normalize_manifest(prev_manifest) != normalize_manifest(manifest)
    if manifest_changed:
        write_manifest(manifest, manifest_path)

    existing_history: list[dict[str, Any]] = []
    if history_path.exists():
        existing_history = json.loads(history_path.read_text(encoding="utf-8"))
    if prev_manifest is None and not existing_history:
        events = seed_history_from_migrations()
    elif prev_manifest is None:
        events = existing_history
    else:
        events = existing_history + append_history_events(prev_manifest, manifest, manifest.get("version"))
    history_changed = events != existing_history or not history_path.exists()
    if history_changed:
        write_manifest(events, history_path)

    return {
        "manifest": manifest,
        "history": events,
        "manifest_changed": manifest_changed,
        "history_changed": history_changed,
        "manifest_path": str(manifest_path),
        "history_path": str(history_path),
    }
