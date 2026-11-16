from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scripts import security_check as sec


def test_run_all_security_checks_clean() -> None:
    """Toàn bộ repository hiện tại phải vượt qua 6/6 bài kiểm tra bảo mật."""
    code = sec.run_all_security_checks(verbose=False)
    assert code == 0


def test_sec01_detects_forbidden_file() -> None:
    """SEC-01 phải phát hiện khi có file bí mật hoặc .env bị git theo dõi."""
    mock_files = ["app/main.py", ".env", "data/test.sqlite"]
    res = sec.check_sec01_secrets(mock_files)
    assert not res.passed
    assert any(".env" in f.message for f in res.findings)


def test_sec02_detects_direct_env_read(tmp_path: Path) -> None:
    """SEC-02 phải phát hiện khi có mã nguồn mở trực tiếp file .env."""
    app_dir = tmp_path / "app"
    app_dir.mkdir(exist_ok=True)
    py_file = app_dir / "bad_reader.py"
    py_file.write_text('with open(".env") as f:\n    pass\n', encoding="utf-8")

    with patch.object(sec, "ROOT", tmp_path):
        res = sec.check_sec02_env_reads(["app/bad_reader.py"])
        assert not res.passed
        assert any("Mở trực tiếp file .env" in f.message for f in res.findings)


def test_sec03_detects_insecure_md5_hash(tmp_path: Path) -> None:
    """SEC-03 phải phát hiện khi có việc dùng hashlib.md5 trong thư mục app."""
    app_dir = tmp_path / "app"
    app_dir.mkdir(exist_ok=True)
    py_file = app_dir / "bad_hash.py"
    py_file.write_text('import hashlib\nh = hashlib.md5(b"test").hexdigest()\n', encoding="utf-8")

    with patch.object(sec, "ROOT", tmp_path):
        res = sec.check_sec03_hashing()
        assert not res.passed
        assert any("md5" in f.message for f in res.findings)
