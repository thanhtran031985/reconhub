#!/usr/bin/env python3
"""ReconHub Automated Security Scanner.

Kiểm tra an toàn và bảo mật tự động theo spec 06 và .agents/rules/security.md:
1. SEC-01: Quét lộ bí mật, khóa riêng tư (private keys), token và file nhạy cảm trong git.
2. SEC-02: Chặn đọc trực tiếp file .env trong mã ứng dụng (buộc dùng pydantic_settings/get_settings).
3. SEC-03: Kiểm tra thuật toán băm (chặn md5/sha1 cho mật khẩu/xác thực; bắt buộc argon2id).
4. SEC-04: Phòng chống SQL Injection và chuỗi format không bind param trong queries.
5. SEC-05: Kiểm tra che giấu dữ liệu nhạy cảm (redaction mật khẩu Data Source trong UI/audit).
6. SEC-06: Baseline cấu hình an toàn (thời hạn phiên, lockout khi đăng nhập sai, giới hạn upload).

Chạy: uv run poe security-check (hoặc python scripts/security_check.py)
Thoát: mã 0 khi toàn bộ kiểm tra đạt, 1 khi có vi phạm.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class Finding:
    check_id: str
    severity: str  # HIGH, MEDIUM, LOW
    file_path: str
    line_number: int | None
    message: str
    snippet: str | None = None


@dataclass
class CheckResult:
    check_id: str
    title: str
    passed: bool
    findings: list[Finding] = field(default_factory=list)


# Các pattern bí mật nguy hiểm
PATTERNS_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP|PRIVATE) KEY-----")
PATTERNS_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
PATTERNS_SLACK_TOKEN = re.compile(r"\bxox[baprs]-[0-9a-zA-Z-]{10,}\b")
PATTERNS_GENERIC_SECRET = re.compile(
    r"""(?i)(?:api_key|secret_key|private_key)\s*[:=]\s*["']([A-Za-z0-9_\-]{20,})["']"""
)
SAFE_SECRET_PLACEHOLDERS = {
    "change_me",
    "placeholder",
    "***",
    "test_secret",
    "dummy",
    "secret",
}


def _get_tracked_files() -> list[str]:
    """Lấy danh sách các file đang được git theo dõi."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        # Dự phòng nếu không có git hoặc chạy môi trường ngoài git
        files: list[str] = []
        for p in ROOT.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.parts):
                files.append(str(p.relative_to(ROOT)).replace("\\", "/"))
        return files


def check_sec01_secrets(tracked_files: list[str]) -> CheckResult:
    """SEC-01: Quét file nhạy cảm và lộ bí mật trong git."""
    findings: list[Finding] = []

    # 1. Kiểm tra các file cấm bị theo dõi
    forbidden_exact = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
    forbidden_suffixes = {".pem", ".key", ".pfx", ".p12", ".sqlite", ".db", ".db-wal"}

    for fpath in tracked_files:
        p = Path(fpath)
        if p.name in forbidden_exact or any(fpath.endswith(suf) for suf in forbidden_suffixes):
            # Bỏ qua sqlite test fixture nếu có khai báo rõ ràng trong tests/
            if "tests/" in fpath and fpath.endswith(".db"):
                continue
            findings.append(
                Finding(
                    check_id="SEC-01",
                    severity="HIGH",
                    file_path=fpath,
                    line_number=None,
                    message=f"File nhạy cảm bị theo dõi bởi git: {fpath}",
                )
            )

    # 2. Quét nội dung các file nguồn
    code_extensions = {".py", ".json", ".yaml", ".yml", ".md", ".toml"}
    scan_dirs = {"app", "worker", "scripts", "migrations"}

    for fpath in tracked_files:
        p = Path(fpath)
        if p.suffix not in code_extensions:
            continue
        if not any(fpath.startswith(d + "/") or fpath.startswith(d + "\\") for d in scan_dirs):
            continue

        abs_path = ROOT / fpath
        if not abs_path.is_file():
            continue

        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Bỏ qua chú thích
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            # Private Key
            if PATTERNS_PRIVATE_KEY.search(line):
                findings.append(
                    Finding(
                        check_id="SEC-01",
                        severity="HIGH",
                        file_path=fpath,
                        line_number=idx,
                        message="Phát hiện Private Key nhúng trực tiếp trong mã nguồn",
                        snippet=stripped[:80],
                    )
                )

            # AWS Key
            if PATTERNS_AWS_KEY.search(line):
                findings.append(
                    Finding(
                        check_id="SEC-01",
                        severity="HIGH",
                        file_path=fpath,
                        line_number=idx,
                        message="Phát hiện AWS Key ID nhúng trực tiếp trong mã nguồn",
                        snippet=stripped[:80],
                    )
                )

            # Slack Token
            if PATTERNS_SLACK_TOKEN.search(line):
                findings.append(
                    Finding(
                        check_id="SEC-01",
                        severity="HIGH",
                        file_path=fpath,
                        line_number=idx,
                        message="Phát hiện Slack Token nhúng trực tiếp trong mã nguồn",
                        snippet=stripped[:80],
                    )
                )

            # Generic Secret
            m = PATTERNS_GENERIC_SECRET.search(line)
            if m:
                val = m.group(1).lower()
                if not any(ph in val for ph in SAFE_SECRET_PLACEHOLDERS):
                    findings.append(
                        Finding(
                            check_id="SEC-01",
                            severity="MEDIUM",
                            file_path=fpath,
                            line_number=idx,
                            message="Nghi vấn bí mật/API key gán tĩnh (hardcoded)",
                            snippet=stripped[:80],
                        )
                    )

    return CheckResult(
        check_id="SEC-01",
        title="Quét lộ bí mật & file nhạy cảm trong git",
        passed=len(findings) == 0,
        findings=findings,
    )


def check_sec02_env_reads(tracked_files: list[str]) -> CheckResult:
    """SEC-02: Chặn mã nguồn đọc trực tiếp file .env."""
    findings: list[Finding] = []
    forbidden_env_patterns = [
        (re.compile(r"""open\s*\(\s*["'][^"']*\.env["']"""), "Mở trực tiếp file .env qua hàm open()"),
        (re.compile(r"""Path\s*\(\s*["'][^"']*\.env["']\s*\)"""), "Đọc file .env qua Path()"),
        (re.compile(r"""\bload_dotenv\s*\("""), "Gọi load_dotenv() trực tiếp"),
        (re.compile(r"""\bdotenv_values\s*\("""), "Gọi dotenv_values() trực tiếp"),
    ]

    for fpath in tracked_files:
        if not fpath.endswith(".py"):
            continue
        if not (fpath.startswith("app/") or fpath.startswith("worker/") or fpath.startswith("scripts/")):
            continue
        # Bỏ qua chính script kiểm tra bảo mật và config
        if fpath in (
            "app/core/config.py",
            "app\\core\\config.py",
            "scripts/security_check.py",
            "scripts\\security_check.py",
        ):
            continue

        abs_path = ROOT / fpath
        if not abs_path.is_file():
            continue

        try:
            lines = abs_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pat, desc in forbidden_env_patterns:
                if pat.search(line):
                    findings.append(
                        Finding(
                            check_id="SEC-02",
                            severity="HIGH",
                            file_path=fpath,
                            line_number=idx,
                            message=f"{desc}. Cần dùng pydantic_settings qua app.core.config.get_settings().",
                            snippet=stripped[:80],
                        )
                    )

    return CheckResult(
        check_id="SEC-02",
        title="Chặn đọc trực tiếp file .env trong mã ứng dụng",
        passed=len(findings) == 0,
        findings=findings,
    )


def check_sec03_hashing() -> CheckResult:
    """SEC-03: Kiểm tra thuật toán băm (chặn md5/sha1 cho mật khẩu/auth; bắt buộc argon2id)."""
    findings: list[Finding] = []
    # 1. Quét tìm md5/sha1 trong app và worker
    for base_dir in ["app", "worker"]:
        dir_path = ROOT / base_dir
        if not dir_path.is_dir():
            continue
        for py_file in dir_path.rglob("*.py"):
            try:
                lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            rel_path = str(py_file.relative_to(ROOT)).replace("\\", "/")
            for idx, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "hashlib.md5" in line or "hashlib.sha1" in line:
                    findings.append(
                        Finding(
                            check_id="SEC-03",
                            severity="HIGH",
                            file_path=rel_path,
                            line_number=idx,
                            message="Sử dụng thuật toán băm yếu (md5/sha1). Cần dùng sha256 hoặc argon2id.",
                            snippet=stripped[:80],
                        )
                    )

    # 2. Xác thực app/core/auth.py sử dụng argon2 PasswordHasher
    auth_py = ROOT / "app" / "core" / "auth.py"
    if auth_py.is_file():
        content = auth_py.read_text(encoding="utf-8", errors="ignore")
        if "PasswordHasher" not in content or "argon2" not in content:
            findings.append(
                Finding(
                    check_id="SEC-03",
                    severity="HIGH",
                    file_path="app/core/auth.py",
                    line_number=1,
                    message="app/core/auth.py không sử dụng argon2-cffi PasswordHasher để băm mật khẩu người dùng.",
                )
            )

    return CheckResult(
        check_id="SEC-03",
        title="Bảo đảm thuật toán băm an toàn (argon2id, không dùng md5/sha1)",
        passed=len(findings) == 0,
        findings=findings,
    )


def check_sec04_sql_safety() -> CheckResult:
    """SEC-04: Phòng chống SQL Injection và chuỗi format không bind param trong queries."""
    findings: list[Finding] = []

    # Quét app/services, app/engine, app/repo
    for base_dir in ["app/services", "app/engine", "app/repo"]:
        p = ROOT / base_dir
        if not p.is_dir():
            continue

        for py_file in p.rglob("*.py"):
            rel_path = str(py_file.relative_to(ROOT)).replace("\\", "/")
            try:
                lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            for idx, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue

                # Cảnh báo raw string formatting kết hợp với WHERE / AND / OR trong câu lệnh query
                if re.search(r"""(?:WHERE|AND|OR)\s+[A-Za-z0-9_]+\s*=\s*['"]?\{[a-zA-Z0-9_]+""", line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            check_id="SEC-04",
                            severity="HIGH",
                            file_path=rel_path,
                            line_number=idx,
                            message="Nghi vấn nội suy f-string trực tiếp vào mệnh đề WHERE/AND/OR SQL mà không dùng bind parameter.",
                            snippet=stripped[:80],
                        )
                    )

    # Kiểm tra sự hiện diện của sql_guard
    sql_guard = ROOT / "app" / "engine" / "sql_guard.py"
    if not sql_guard.is_file():
        findings.append(
            Finding(
                check_id="SEC-04",
                severity="HIGH",
                file_path="app/engine/sql_guard.py",
                line_number=None,
                message="Thiếu module kiểm soát SQL an toàn (sql_guard.py).",
            )
        )

    return CheckResult(
        check_id="SEC-04",
        title="Kiểm soát SQL Injection & ép buộc bind parameter",
        passed=len(findings) == 0,
        findings=findings,
    )


def check_sec05_data_source_redaction() -> CheckResult:
    """SEC-05: Kiểm tra che giấu dữ liệu nhạy cảm (mật khẩu Data Source trong UI/audit)."""
    findings: list[Finding] = []

    # Kiểm tra app/services/data_source.py đảm bảo mật khẩu trả về được che giấu '***'
    ds_service = ROOT / "app" / "services" / "data_source.py"
    if ds_service.is_file():
        content = ds_service.read_text(encoding="utf-8", errors="ignore")
        if '"password": "***"' not in content and "'password': '***'" not in content:
            findings.append(
                Finding(
                    check_id="SEC-05",
                    severity="HIGH",
                    file_path="app/services/data_source.py",
                    line_number=None,
                    message="Không tìm thấy logic che giấu mật khẩu (password: '***') trong phản hồi Data Source.",
                )
            )
        if "PASSWORD_ENC" in content and "old_data" in content:
            if 'k != "PASSWORD_ENC"' not in content:
                findings.append(
                    Finding(
                        check_id="SEC-05",
                        severity="MEDIUM",
                        file_path="app/services/data_source.py",
                        line_number=None,
                        message="Cần loại bỏ PASSWORD_ENC khỏi audit log old_data/new_data.",
                    )
                )

    # Kiểm tra app/core/crypto.py có hàm mã hóa Fernet cho bí mật
    crypto_py = ROOT / "app" / "core" / "crypto.py"
    if not crypto_py.is_file():
        findings.append(
            Finding(
                check_id="SEC-05",
                severity="HIGH",
                file_path="app/core/crypto.py",
                line_number=None,
                message="Thiếu module mã hóa bí mật Fernet (crypto.py).",
            )
        )

    return CheckResult(
        check_id="SEC-05",
        title="Che giấu bí mật Data Source & mã hóa Fernet",
        passed=len(findings) == 0,
        findings=findings,
    )


def check_sec06_baseline_config() -> CheckResult:
    """SEC-06: Baseline cấu hình an toàn (thời hạn phiên, lockout, giới hạn upload)."""
    findings: list[Finding] = []

    try:
        from app.core.config import Settings

        s = Settings()
        if s.SESSION_HOURS > 24 or s.SESSION_HOURS <= 0:
            findings.append(
                Finding(
                    check_id="SEC-06",
                    severity="MEDIUM",
                    file_path="app/core/config.py",
                    line_number=None,
                    message=f"SESSION_HOURS ({s.SESSION_HOURS}) ngoài khoảng an toàn đề xuất (1 - 24 giờ).",
                )
            )

        if s.LOGIN_MAX_FAILS > 10 or s.LOGIN_MAX_FAILS <= 0:
            findings.append(
                Finding(
                    check_id="SEC-06",
                    severity="MEDIUM",
                    file_path="app/core/config.py",
                    line_number=None,
                    message=f"LOGIN_MAX_FAILS ({s.LOGIN_MAX_FAILS}) quá lớn hoặc không hợp lệ.",
                )
            )

        if s.LOGIN_LOCK_MINUTES < 5:
            findings.append(
                Finding(
                    check_id="SEC-06",
                    severity="MEDIUM",
                    file_path="app/core/config.py",
                    line_number=None,
                    message=f"LOGIN_LOCK_MINUTES ({s.LOGIN_LOCK_MINUTES}) quá ngắn (tối thiểu 5 phút).",
                )
            )

        if s.MAX_UPLOAD_SIZE_MB > 200 or s.MAX_UPLOAD_SIZE_MB <= 0:
            findings.append(
                Finding(
                    check_id="SEC-06",
                    severity="MEDIUM",
                    file_path="app/core/config.py",
                    line_number=None,
                    message=f"MAX_UPLOAD_SIZE_MB ({s.MAX_UPLOAD_SIZE_MB}) vượt quá giới hạn an toàn khuyến nghị.",
                )
            )
    except Exception as exc:
        findings.append(
            Finding(
                check_id="SEC-06",
                severity="HIGH",
                file_path="app/core/config.py",
                line_number=None,
                message=f"Lỗi khi kiểm tra cấu hình Settings: {exc}",
            )
        )

    # Kiểm tra xác thực magic bytes trong file_service
    file_service_py = ROOT / "app" / "services" / "file_service.py"
    if file_service_py.is_file():
        content = file_service_py.read_text(encoding="utf-8", errors="ignore")
        if "_validate_magic_bytes" not in content:
            findings.append(
                Finding(
                    check_id="SEC-06",
                    severity="HIGH",
                    file_path="app/services/file_service.py",
                    line_number=None,
                    message="Thiếu hàm xác thực magic bytes cho file tải lên.",
                )
            )

    return CheckResult(
        check_id="SEC-06",
        title="Baseline cấu hình bảo mật ứng dụng",
        passed=len(findings) == 0,
        findings=findings,
    )


def run_all_security_checks(verbose: bool = False) -> int:
    """Chạy toàn bộ các bài kiểm tra bảo mật."""
    print("=" * 60)
    print("      RECONHUB AUTOMATED SECURITY SCANNER")
    print("=" * 60)

    tracked_files = _get_tracked_files()

    checks = [
        check_sec01_secrets(tracked_files),
        check_sec02_env_reads(tracked_files),
        check_sec03_hashing(),
        check_sec04_sql_safety(),
        check_sec05_data_source_redaction(),
        check_sec06_baseline_config(),
    ]

    total = len(checks)
    passed_count = 0
    all_findings: list[Finding] = []

    for c in checks:
        if c.passed:
            passed_count += 1
            print(f"[PASS] {c.check_id}: {c.title}")
        else:
            print(f"[FAIL] {c.check_id}: {c.title} ({len(c.findings)} vi phạm)")
            all_findings.extend(c.findings)
            for f in c.findings:
                loc = f"{f.file_path}:{f.line_number}" if f.line_number else f.file_path
                print(f"       [{f.severity}] {loc} — {f.message}")
                if f.snippet and verbose:
                    print(f"       >> {f.snippet}")

    print("-" * 60)
    print(f"Kết quả: {passed_count}/{total} bài kiểm tra ĐẠT. ({len(all_findings)} vi phạm)")

    if passed_count == total:
        print("Trạng thái: AN TOÀN — Không phát hiện lỗ hổng bảo mật nào.")
        print("=" * 60)
        return 0
    else:
        print("Trạng thái: NGUY HIỂM — Cần khắc phục các vi phạm trước khi đóng task.")
        print("=" * 60)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ReconHub Automated Security Scanner")
    parser.add_argument("-v", "--verbose", action="store_true", help="Hiển thị chi tiết snippet mã vi phạm")
    args = parser.parse_args(argv)
    return run_all_security_checks(verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
