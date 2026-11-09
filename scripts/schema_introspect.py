#!/usr/bin/env python3
"""CLI Schema Inspector — sinh schema-manifest.json + schema-history.json.

Chạy: uv run poe schema-introspect [--check] [--out DIR] [--db-url URL]
Chế độ --check chỉ so sánh (không ghi file), dùng cho CI freshness.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services import schema_inspector as si  # noqa: E402

DEFAULT_OUT = ROOT / "docs" / "data-model"


def _check(out_dir: Path) -> int:
    """Generate manifest vào thư mục tạm rồi normalize-compare với file đã commit."""
    manifest_path = out_dir / "schema-manifest.json"
    if not manifest_path.exists():
        print("Schema manifest is stale. Run: uv run poe schema-introspect")
        return 1
    committed = json.loads(manifest_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        result = si.generate_all(Path(tmp))
        fresh = result["manifest"]
    if si.normalize_manifest(committed) != si.normalize_manifest(fresh):
        print("Schema manifest is stale. Run: uv run poe schema-introspect")
        return 1
    print("Schema manifest is up to date.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Schema Inspector: sinh schema manifest/history.")
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra manifest đã commit có mới không.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Thư mục ghi artifact (mặc định docs/data-model).")
    parser.add_argument("--db-url", default=None, help="URL database app (mặc định từ settings).")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    if args.check:
        return _check(out_dir)

    db_url = args.db_url or get_settings().effective_db_url
    result = si.generate_all(out_dir, db_url=db_url)
    print(f"Manifest: {result['manifest_path']} ({len(result['manifest']['tables'])} tables)")
    print(f"History: {result['history_path']} ({len(result['history'])} events)")
    print(f"Manifest changed: {result['manifest_changed']}, history changed: {result['history_changed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
