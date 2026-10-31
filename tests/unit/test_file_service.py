from __future__ import annotations

from pathlib import Path

import pytest

from app.core.context import Ctx, Role
from app.schemas.errors import ErrorCode
from app.services.file_service import get_file, upload_file


@pytest.fixture
def op_ctx() -> Ctx:
    return Ctx(
        user_id=1,
        username="operator",
        full_name="Operator User",
        roles=[Role.OPERATOR],
    )


def test_upload_valid_xlsx(op_ctx: Ctx) -> None:
    sample_path = Path("samples/dtp_sample_200.xlsx")
    content = sample_path.read_bytes()

    res = upload_file(op_ctx, filename="dtp_sample.xlsx", content=content)
    assert res.ok is True
    data = res.data
    assert data["id"] > 0
    assert len(data["sha256"]) == 64
    assert data["original_name"] == "dtp_sample.xlsx"
    assert "BÁO CÁO DTP" in data["sheets"]
    assert Path(data["storage_path"]).exists()

    # Kiểm tra get_file
    f_res = get_file(op_ctx, data["id"])
    assert f_res.ok is True
    f_info = f_res.data
    assert f_info["id"] == data["id"]
    assert f_info["original_name"] == "dtp_sample.xlsx"
    assert Path(f_info["storage_path"]).exists()


def test_upload_invalid_magic_bytes(op_ctx: Ctx) -> None:
    # File text nhưng giả danh đuôi .xlsx
    fake_content = b"This is just plain text, not a zip file."
    res = upload_file(op_ctx, filename="fake.xlsx", content=fake_content)
    assert res.ok is False
    assert res.code == ErrorCode.FILE_TYPE_NOT_ALLOWED


def test_upload_unsupported_extension(op_ctx: Ctx) -> None:
    res = upload_file(op_ctx, filename="script.exe", content=b"MZ\x90\x00")
    assert res.ok is False
    assert res.code == ErrorCode.FILE_TYPE_NOT_ALLOWED


def test_upload_oversize_file(op_ctx: Ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    # Giả lập giới hạn upload tối đa 0 MB để test
    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_SIZE_MB", 0)
    res = upload_file(op_ctx, filename="test.xlsx", content=b"PK\x03\x04" + b"x" * 2000)
    assert res.ok is False
    assert res.code == ErrorCode.FILE_TOO_LARGE
