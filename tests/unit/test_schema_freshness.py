"""Tests cho CI freshness --check — Bước 2 task 31 (test viết trước)."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from app.services import schema_inspector as si

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "schema_introspect.py"
STALE_MSG = "Schema manifest is stale. Run: uv run poe schema-introspect"


def _run_check(out_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--out", str(out_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _hashes(out_dir: Path) -> dict[str, str]:
    result = {}
    for path in sorted(out_dir.iterdir()):
        result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def test_check_exit_0_when_synced(tmp_path):
    out_dir = tmp_path / "data-model"
    si.generate_all(out_dir)
    before = _hashes(out_dir)
    proc = _run_check(out_dir)
    assert proc.returncode == 0
    assert "up to date" in proc.stdout
    assert _hashes(out_dir) == before  # --check không ghi file.


def test_check_exit_1_and_message_when_stale(tmp_path):
    out_dir = tmp_path / "data-model"
    si.generate_all(out_dir)
    manifest_path = out_dir / "schema-manifest.json"
    text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(text.replace("Lần chạy đối soát", "MÔ TẢ GIẢ", 1), encoding="utf-8")
    before = _hashes(out_dir)
    proc = _run_check(out_dir)
    assert proc.returncode == 1
    assert STALE_MSG in proc.stdout
    assert _hashes(out_dir) == before  # --check không ghi file.


def test_check_exit_1_when_manifest_missing(tmp_path):
    out_dir = tmp_path / "data-model"
    out_dir.mkdir()
    proc = _run_check(out_dir)
    assert proc.returncode == 1
    assert STALE_MSG in proc.stdout


def test_check_committed_manifest_is_fresh():
    """Manifest đã commit trong repo phải đồng bộ (bảo vệ bởi CI)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
