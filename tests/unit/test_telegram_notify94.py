"""Task 94 — báo run DONE/FAILED qua Telegram cho người chạy.

Tests-first (plan bước 2): build tin DONE/FAILED đúng số đếm; cổng gửi
mock urllib; gate chưa liên kết/công tắc tắt; liên kết bằng mã qua /start;
token lưu mã hóa; hồi quy notify_for_run trong app.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine, select

from app.core.auth import hash_password
from app.core.context import Ctx
from app.db.metadata import (
    metadata,
    recon_app_setting,
    recon_data_source,
    recon_file,
    recon_notification,
    recon_notification_pref,
    recon_run,
    recon_run_summary,
    recon_template,
    recon_template_version,
    recon_user,
)
from app.services.telegram_notify import (
    generate_link_code,
    get_telegram_settings,
    is_telegram_enabled,
    notify_telegram_for_run,
    poll_telegram_updates_once,
    send_telegram_message,
    send_telegram_test,
    set_telegram_enabled,
    set_telegram_settings,
    unlink_telegram,
)

RUN_DONE_ID = 1040
RUN_FAILED_ID = 1041
BOT_TOKEN = "123456789:AAEhBOweik6ad9r_QXMENQjcrGbqCrO9_8"
BOT_USERNAME = "reconhub_test_bot"
ADMIN_CHAT_ID = "987654321"
LONG_ERROR = "Lỗi chi tiết. " * 100  # 1400 ký tự, vượt giới hạn 500


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def tg_env(tmp_path, monkeypatch):
    db_file = tmp_path / "telegram_notify94_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    engine = create_engine(db_url)
    metadata.create_all(engine)
    monkeypatch.setattr("app.services.telegram_notify.get_recon_engine", lambda: engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)
    now = _now()
    with engine.begin() as conn:
        for uid, username in [(1, "admin"), (2, "operator")]:
            conn.execute(
                recon_user.insert().values(
                    ID=uid,
                    USERNAME=username,
                    FULL_NAME=username,
                    PASSWORD_HASH=hash_password("admin123"),
                    IS_ACTIVE="Y",
                    MUST_CHANGE_PW="N",
                    SESSION_VERSION=1,
                    CREATED_BY="system",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                )
            )
        seed_perm_basics(engine, {1: ["ADMIN"], 2: ["OPERATOR"]}, conn=conn)
        res_ds = conn.execute(
            recon_data_source.insert().values(
                NAME="GMD_DEV",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="TESTSVC",
                USERNAME="recon_test",
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="test",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = res_ds.inserted_primary_key[0]
        res_f = conn.execute(
            recon_file.insert().values(
                ORIGINAL_NAME="vtos_2026-07.xlsx",
                SIZE_BYTES=31000,
                SHA256="abc12345",
                STORAGE_PATH="vtos_2026-07.xlsx",
                UPLOADED_BY="admin",
                UPLOADED_AT=now,
            )
        )
        f_id = res_f.inserted_primary_key[0]
        res_t = conn.execute(
            recon_template.insert().values(
                CODE="BILL_VTOS",
                NAME="Doanh thu Vtos",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                ROW_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        tmpl_id = res_t.inserted_primary_key[0]
        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tmpl_id,
                VERSION=1,
                STATUS="ACTIVE",
                CONFIG_JSON={},
                DATA_SOURCE_ID=ds_id,
                DRY_RUN_OK="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                ACTIVATED_AT=now,
            )
        )
        conn.execute(
            recon_run.insert().values(
                ID=RUN_DONE_ID,
                TEMPLATE_ID=tmpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="BY_INVOICE_VTOS",
                DATA_SOURCE_ID=ds_id,
                FILE_ID=f_id,
                SHEET_NAME="Sheet1",
                STATUS="DONE",
                STAGE="DONE",
                PROGRESS_PCT=100,
                P_FROM=datetime(2026, 7, 1, 0, 0, 0),
                P_TO=datetime(2026, 7, 31, 23, 59, 59),
                CREATED_BY="admin",
                CREATED_AT=now,
                STARTED_AT=now,
                FINISHED_AT=now,
            )
        )
        conn.execute(
            recon_run_summary.insert().values(
                RUN_ID=RUN_DONE_ID,
                EXCEL_ROWS_READ=10749,
                EXCEL_GROUPS=6718,
                DB_ROWS=1073,
                DB_GROUPS=1073,
                CNT_MATCHED=604,
                CNT_MISMATCH=0,
                CNT_MISSING_IN_DB=6114,
                CNT_MISSING_IN_EXCEL=469,
                CNT_INCONSISTENT=0,
                CNT_DUPLICATE=0,
                DURATION_MS=1000,
            )
        )
        conn.execute(
            recon_run.insert().values(
                ID=RUN_FAILED_ID,
                TEMPLATE_ID=tmpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="BY_INVOICE_VTOS",
                DATA_SOURCE_ID=ds_id,
                FILE_ID=f_id,
                SHEET_NAME="Sheet1",
                STATUS="FAILED",
                STAGE="ERROR",
                PROGRESS_PCT=0,
                P_FROM=datetime(2026, 7, 1, 0, 0, 0),
                P_TO=datetime(2026, 7, 31, 23, 59, 59),
                ERROR_CODE="INTERNAL_ERROR",
                ERROR_MSG=LONG_ERROR,
                CREATED_BY="admin",
                CREATED_AT=now,
                STARTED_AT=now,
                FINISHED_AT=now,
            )
        )
    return {"engine": engine, "ds_id": int(ds_id), "tmpl_id": int(tmpl_id)}


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


@pytest.fixture
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])


def _set_chat(engine: Any, user_id: int, chat_id: str | None) -> None:
    with engine.begin() as conn:
        conn.execute(recon_user.update().where(recon_user.c.ID == user_id).values(TELEGRAM_CHAT_ID=chat_id))


def _set_pref(engine: Any, user_id: int, event_type: str, enabled: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            recon_notification_pref.insert().values(
                USER_ID=user_id, EVENT_TYPE=event_type, ENABLED=enabled, UPDATED_AT=_now()
            )
        )


def _set_bot(engine: Any, token: str = BOT_TOKEN, username: str = BOT_USERNAME) -> None:
    from app.core.crypto import encrypt_secret

    with engine.begin() as conn:
        for key, value in (
            ("TELEGRAM_BOT_TOKEN", encrypt_secret(token)),
            ("TELEGRAM_BOT_USERNAME", username),
        ):
            conn.execute(recon_app_setting.insert().values(KEY=key, VALUE=value, UPDATED_BY="admin", UPDATED_AT=_now()))


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _fake_urlopen(
    calls: list[dict[str, Any]], get_updates: dict[str, Any] | None = None, fail_with: BaseException | None = None
):
    """Fake urllib.request.urlopen: ghi lại (url, data) mọi lần gọi."""

    def _open(url_or_req: Any, timeout: Any = None) -> _FakeResponse:
        if isinstance(url_or_req, urllib.request.Request):
            url = url_or_req.full_url
            data = url_or_req.data
        else:
            url, data = str(url_or_req), None
        calls.append({"url": url, "data": data})
        if fail_with is not None:
            raise fail_with
        if "getUpdates" in url:
            return _FakeResponse(get_updates if get_updates is not None else {"ok": True, "result": []})
        return _FakeResponse({"ok": True, "result": {"message_id": 1}})

    return _open


def _send_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in calls:
        if "sendMessage" in c["url"]:
            out.append(json.loads(c["data"].decode("utf-8")) if c["data"] else {})
    return out


class TestBuildMessage:
    def test_done_message_counts(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        _set_bot(engine)
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert notify_telegram_for_run(engine, RUN_DONE_ID, "RUN_DONE") is True
        assert len(calls) == 1
        assert calls[0]["url"] == f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        body = json.loads(calls[0]["data"].decode("utf-8"))
        assert body["chat_id"] == ADMIN_CHAT_ID
        assert body["text"] == (
            "Run #1040 đã xong — Doanh thu Vtos, kỳ 2026-07: Khớp 604 · Lệch 0 · "
            "Thiếu trong DB 6.114 · Thiếu trong Excel 469."
        )

    def test_done_message_without_summary(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        _set_bot(engine)
        with engine.begin() as conn:
            conn.execute(recon_run_summary.delete().where(recon_run_summary.c.RUN_ID == RUN_DONE_ID))
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert notify_telegram_for_run(engine, RUN_DONE_ID, "RUN_DONE") is True
        assert _send_calls(calls)[0]["text"] == "Run #1040 đã xong — Doanh thu Vtos, kỳ 2026-07."

    def test_failed_message_truncated(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        _set_bot(engine)
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert notify_telegram_for_run(engine, RUN_FAILED_ID, "RUN_FAILED") is True
        assert _send_calls(calls)[0]["text"] == f"Run #1041 lỗi — {LONG_ERROR[:500]}."

    def test_unknown_run_returns_false(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        _set_bot(engine)
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert notify_telegram_for_run(engine, 9999, "RUN_DONE") is False
        assert calls == []

    def test_unknown_event_returns_false(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        _set_bot(engine)
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert notify_telegram_for_run(engine, RUN_DONE_ID, "REPORT_RUN_DONE") is False
        assert calls == []


class TestSendGate:
    def test_send_success(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_bot(engine)
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert send_telegram_message(ADMIN_CHAT_ID, "hello", engine) is True
        assert calls[0]["url"] == f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        assert json.loads(calls[0]["data"].decode("utf-8")) == {"chat_id": ADMIN_CHAT_ID, "text": "hello"}

    def test_send_http_error_returns_false(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_bot(engine)
        calls: list[dict[str, Any]] = []
        err = urllib.error.HTTPError("http://x", 403, "Forbidden", {}, None)
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls, fail_with=err))
        assert send_telegram_message(ADMIN_CHAT_ID, "hello", engine) is False
        assert len(calls) == 1

    def test_send_timeout_returns_false(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_bot(engine)
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls, fail_with=TimeoutError("timed out")))
        assert send_telegram_message(ADMIN_CHAT_ID, "hello", engine) is False

    def test_not_linked_no_send(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_bot(engine)
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert notify_telegram_for_run(engine, RUN_DONE_ID, "RUN_DONE") is False
        assert calls == []

    def test_telegram_pref_off_no_send(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        _set_bot(engine)
        _set_pref(engine, 1, "TELEGRAM", "N")
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert notify_telegram_for_run(engine, RUN_DONE_ID, "RUN_DONE") is False
        assert calls == []

    def test_telegram_pref_on_sends(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        _set_bot(engine)
        _set_pref(engine, 1, "TELEGRAM", "Y")
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert notify_telegram_for_run(engine, RUN_DONE_ID, "RUN_DONE") is True
        assert len(_send_calls(calls)) == 1

    def test_inapp_run_done_pref_off_still_sends(self, tg_env, monkeypatch):
        """Telegram độc lập với pref trong app: RUN_DONE trong app TẮT vẫn gửi."""
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        _set_bot(engine)
        _set_pref(engine, 1, "RUN_DONE", "N")
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert is_telegram_enabled(engine, 1, "RUN_DONE") is True
        assert notify_telegram_for_run(engine, RUN_DONE_ID, "RUN_DONE") is True
        assert len(_send_calls(calls)) == 1

    def test_no_token_no_send(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert send_telegram_message(ADMIN_CHAT_ID, "hello", engine) is False
        assert calls == []

    def test_corrupt_token_no_send(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        # Lưu thẳng giá trị hỏng (không phải Fernet) để decrypt lỗi.
        with engine.begin() as conn:
            conn.execute(
                recon_app_setting.insert().values(
                    KEY="TELEGRAM_BOT_TOKEN",
                    VALUE="khong-phai-fernet",
                    UPDATED_BY="admin",
                    UPDATED_AT=_now(),
                )
            )
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert send_telegram_message(ADMIN_CHAT_ID, "hello", engine) is False
        assert calls == []


class TestSettings:
    def test_set_token_encrypted(self, tg_env, admin_ctx):
        engine = tg_env["engine"]
        res = set_telegram_settings(admin_ctx, BOT_TOKEN, "@TestBot")
        assert res.ok, res.message
        with engine.connect() as conn:
            stored = conn.execute(
                select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "TELEGRAM_BOT_TOKEN")
            ).scalar_one()
            username = conn.execute(
                select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "TELEGRAM_BOT_USERNAME")
            ).scalar_one()
        assert BOT_TOKEN not in stored
        from app.core.crypto import decrypt_secret

        assert decrypt_secret(stored) == BOT_TOKEN
        assert username == "TestBot"

    def test_get_settings_no_token_leak(self, tg_env, admin_ctx):
        set_telegram_settings(admin_ctx, BOT_TOKEN, "TestBot")
        res = get_telegram_settings(admin_ctx)
        assert res.ok, res.message
        assert set(res.data.keys()) == {"configured", "username"}
        assert res.data == {"configured": True, "username": "TestBot"}

    def test_set_token_keeps_existing_when_empty(self, tg_env, admin_ctx):
        engine = tg_env["engine"]
        assert set_telegram_settings(admin_ctx, BOT_TOKEN, "TestBot").ok
        with engine.connect() as conn:
            before = conn.execute(
                select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "TELEGRAM_BOT_TOKEN")
            ).scalar_one()
        assert set_telegram_settings(admin_ctx, "", "TestBot").ok
        with engine.connect() as conn:
            after = conn.execute(
                select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "TELEGRAM_BOT_TOKEN")
            ).scalar_one()
        assert after == before

    def test_set_invalid_token_rejected(self, tg_env, admin_ctx):
        res = set_telegram_settings(admin_ctx, "abc", "TestBot")
        assert not res.ok

    def test_non_admin_cannot_set(self, tg_env, operator_ctx):
        res = set_telegram_settings(operator_ctx, BOT_TOKEN, "TestBot")
        assert not res.ok

    def test_send_test_requires_link(self, tg_env, admin_ctx, monkeypatch):
        engine = tg_env["engine"]
        _set_bot(engine)
        res = send_telegram_test(admin_ctx)
        assert not res.ok
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        res = send_telegram_test(admin_ctx)
        assert res.ok, res.message
        assert _send_calls(calls)[0]["text"] == "Tin thử từ ReconHub — bot Telegram đã nối."


class TestLinking:
    def test_generate_link_code(self, tg_env, admin_ctx):
        engine = tg_env["engine"]
        set_telegram_settings(admin_ctx, BOT_TOKEN, BOT_USERNAME)
        res = generate_link_code(admin_ctx)
        assert res.ok, res.message
        code = res.data["code"]
        assert len(code) == 8
        assert res.data["link"] == f"https://t.me/{BOT_USERNAME}?start={code}"
        with engine.connect() as conn:
            row = conn.execute(
                select(recon_user.c.TELEGRAM_LINK_CODE, recon_user.c.TELEGRAM_LINK_EXPIRES_AT).where(
                    recon_user.c.ID == 1
                )
            ).first()
        assert row[0] == code
        assert _now() < row[1] <= _now() + timedelta(minutes=15, seconds=5)

    def test_generate_link_code_no_username(self, tg_env, admin_ctx):
        res = generate_link_code(admin_ctx)
        assert not res.ok

    def test_poll_links_user(self, tg_env, admin_ctx, monkeypatch):
        engine = tg_env["engine"]
        set_telegram_settings(admin_ctx, BOT_TOKEN, BOT_USERNAME)
        code = generate_link_code(admin_ctx).data["code"]
        fixture = {
            "ok": True,
            "result": [
                {
                    "update_id": 10,
                    "message": {"chat": {"id": 555}, "text": f"/start {code}", "from": {"username": "admin"}},
                }
            ],
        }
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls, get_updates=fixture))
        assert poll_telegram_updates_once(engine) == 1
        with engine.connect() as conn:
            row = conn.execute(
                select(
                    recon_user.c.TELEGRAM_CHAT_ID,
                    recon_user.c.TELEGRAM_LINK_CODE,
                    recon_app_setting.c.VALUE,
                )
                .select_from(recon_user)
                .outerjoin(recon_app_setting, recon_app_setting.c.KEY == "TELEGRAM_UPDATE_OFFSET")
                .where(recon_user.c.ID == 1)
            ).first()
        assert row[0] == "555"
        assert row[1] is None
        assert row[2] == "10"
        sent = _send_calls(calls)
        assert len(sent) == 1
        assert sent[0]["chat_id"] == 555
        assert sent[0]["text"] == ("Đã liên kết Telegram với tài khoản admin. Run đối soát xong/lỗi sẽ báo về đây.")

    def test_poll_wrong_code_sends_guidance(self, tg_env, admin_ctx, monkeypatch):
        engine = tg_env["engine"]
        set_telegram_settings(admin_ctx, BOT_TOKEN, BOT_USERNAME)
        generate_link_code(admin_ctx)
        fixture = {
            "ok": True,
            "result": [
                {"update_id": 11, "message": {"chat": {"id": 777}, "text": "/start SAI12345"}},
            ],
        }
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls, get_updates=fixture))
        assert poll_telegram_updates_once(engine) == 1
        with engine.connect() as conn:
            chat = conn.execute(select(recon_user.c.TELEGRAM_CHAT_ID).where(recon_user.c.ID == 1)).scalar_one()
        assert chat is None
        sent = _send_calls(calls)
        assert len(sent) == 1
        assert "Lấy mã liên kết" in sent[0]["text"]

    def test_poll_start_without_code_sends_guidance(self, tg_env, admin_ctx, monkeypatch):
        engine = tg_env["engine"]
        set_telegram_settings(admin_ctx, BOT_TOKEN, BOT_USERNAME)
        fixture = {
            "ok": True,
            "result": [{"update_id": 12, "message": {"chat": {"id": 777}, "text": "/start"}}],
        }
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls, get_updates=fixture))
        assert poll_telegram_updates_once(engine) == 1
        sent = _send_calls(calls)
        assert len(sent) == 1
        assert "Lấy mã liên kết" in sent[0]["text"]

    def test_poll_expired_code_no_link(self, tg_env, admin_ctx, monkeypatch):
        engine = tg_env["engine"]
        set_telegram_settings(admin_ctx, BOT_TOKEN, BOT_USERNAME)
        code = generate_link_code(admin_ctx).data["code"]
        with engine.begin() as conn:
            conn.execute(
                recon_user.update()
                .where(recon_user.c.ID == 1)
                .values(TELEGRAM_LINK_EXPIRES_AT=_now() - timedelta(minutes=1))
            )
        fixture = {
            "ok": True,
            "result": [
                {"update_id": 13, "message": {"chat": {"id": 555}, "text": f"/start {code}"}},
            ],
        }
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls, get_updates=fixture))
        assert poll_telegram_updates_once(engine) == 1
        with engine.connect() as conn:
            chat = conn.execute(select(recon_user.c.TELEGRAM_CHAT_ID).where(recon_user.c.ID == 1)).scalar_one()
        assert chat is None

    def test_poll_getupdates_error_returns_zero(self, tg_env, admin_ctx, monkeypatch):
        engine = tg_env["engine"]
        set_telegram_settings(admin_ctx, BOT_TOKEN, BOT_USERNAME)
        calls: list[dict[str, Any]] = []
        err = urllib.error.HTTPError("http://x", 500, "Server Error", {}, None)
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls, fail_with=err))
        assert poll_telegram_updates_once(engine) == 0

    def test_poll_no_token_returns_zero(self, tg_env, monkeypatch):
        engine = tg_env["engine"]
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(calls))
        assert poll_telegram_updates_once(engine) == 0
        assert calls == []

    def test_unlink(self, tg_env, admin_ctx):
        engine = tg_env["engine"]
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        _set_pref(engine, 1, "TELEGRAM", "Y")
        res = unlink_telegram(admin_ctx)
        assert res.ok, res.message
        with engine.connect() as conn:
            chat = conn.execute(select(recon_user.c.TELEGRAM_CHAT_ID).where(recon_user.c.ID == 1)).scalar_one()
            pref = conn.execute(
                select(recon_notification_pref.c.ENABLED).where(
                    recon_notification_pref.c.USER_ID == 1,
                    recon_notification_pref.c.EVENT_TYPE == "TELEGRAM",
                )
            ).scalar_one()
        assert chat is None
        assert pref == "N"

    def test_set_telegram_enabled(self, tg_env, admin_ctx):
        engine = tg_env["engine"]
        assert set_telegram_enabled(admin_ctx, False).ok
        assert is_telegram_enabled(engine, 1, "RUN_DONE") is False
        assert set_telegram_enabled(admin_ctx, True).ok
        _set_chat(engine, 1, ADMIN_CHAT_ID)
        assert is_telegram_enabled(engine, 1, "RUN_DONE") is True


class TestRegression:
    def test_notify_for_run_unchanged(self, tg_env):
        from app.services.notification import notify_for_run

        engine = tg_env["engine"]
        # RUN_FAILED mặc định BẬT trong app → tạo thông báo.
        assert notify_for_run(engine, RUN_FAILED_ID, "RUN_FAILED", "lỗi", "lý do") is True
        with engine.connect() as conn:
            count = conn.execute(
                select(recon_notification.c.ID).where(recon_notification.c.RELATED_ID == RUN_FAILED_ID)
            ).fetchall()
        assert len(count) == 1
        # RUN_DONE mặc định TẮT trong app → không tạo thông báo.
        assert notify_for_run(engine, RUN_DONE_ID, "RUN_DONE", "xong", "xong") is False
