"""Playwright E2E cho Model Center (/report-models) và Model Studio (/report-models/<id>).

Kiểm thử trình duyệt Chromium thật tại 1440×900 (Light & Dark), 1366×768 và 390×844:
- Đăng nhập, tạo Model mới từ Model Center, kiểm tra /report-models/<id>/edit redirect
- Thêm bảng FACT_SALES & DIM_CUSTOMER từ Source Picker Drawer
- Auto Layout Star Schema, Fit canvas, kéo thả card trên canvas, Lưu nháp
- Thiết lập Table Grain, Measure Studio (TOTAL_REV), Kiểm tra model (Validation Drawer)
- Phát hành với Change Note -> chuyển sang ACTIVE chỉ đọc + Tạo bản nháp mới
- Kiểm tra console errors / HTTP >=400 / horizontal & vertical overflow ở mọi viewport
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page, sync_playwright
from sqlalchemy import create_engine, text

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_data_source, recon_user
from app.engine.catalog import invalidate_catalog_cache
from app.services.perm import clear_perm_cache


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _seed_source_db(src_path: Path) -> None:
    eng = create_engine(f"sqlite:///{src_path.as_posix()}")
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE DIM_CUSTOMER ("
                "CUSTOMER_ID INTEGER PRIMARY KEY, "
                "CUSTOMER_NAME TEXT NOT NULL, "
                "REGION TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE FACT_SALES ("
                "SALES_ID INTEGER PRIMARY KEY, "
                "CUSTOMER_ID INTEGER NOT NULL REFERENCES DIM_CUSTOMER(CUSTOMER_ID), "
                "TRANS_DATE DATE NOT NULL, "
                "NOTE_TXT TEXT, "
                "AMOUNT NUMERIC NOT NULL)"
            )
        )
        conn.execute(text("CREATE VIEW V_CUSTOMER_ACTIVE AS SELECT CUSTOMER_ID, CUSTOMER_NAME FROM DIM_CUSTOMER"))
        conn.execute(text("INSERT INTO DIM_CUSTOMER VALUES (1, 'Cong ty A', 'HN'), (2, 'Cong ty B', 'HCM')"))
        conn.execute(
            text(
                "INSERT INTO FACT_SALES VALUES "
                "(101, 1, '2026-11-01', 'Don 1', 150000), "
                "(102, 2, '2026-11-02', 'Don 2', 250000)"
            )
        )
    eng.dispose()


@pytest.fixture()
def live_studio_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    invalidate_user_session_cache()
    invalidate_catalog_cache()
    clear_perm_cache()

    app_db = tmp_path / "e2e_model_studio_app.db"
    src_db = tmp_path / "e2e_model_studio_src.db"
    _seed_source_db(src_db)

    db_url = f"sqlite:///{app_db.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-model-studio-playwright-secret")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res_u = conn.execute(
            recon_user.insert().values(
                USERNAME="e2e_owner",
                FULL_NAME="E2E Model Owner",
                PASSWORD_HASH=hash_password("Owner@123456"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        uid = int(res_u.inserted_primary_key[0])  # type: ignore[index]
        seed_perm_basics(engine, {uid: ["ADMIN", "TEMPLATE_OWNER"]}, conn=conn)

        conn.execute(
            recon_data_source.insert().values(
                NAME="SRC_E2E_SQLITE",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="SQLITE",
                FILE_PATH=str(src_db),
                DEFAULT_SCHEMA="main",
                CALL_TIMEOUT_S=60,
                MAX_ROWS=10000,
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="e2e_owner",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
    engine.dispose()

    port = _find_free_port()
    srv_env = os.environ.copy()
    srv_env["RECON_DB_URL"] = db_url
    srv_env["FLASK_SECRET_KEY"] = "test-model-studio-playwright-secret"
    srv_code = (
        "from werkzeug.serving import make_server; "
        "from app.ui.app import create_app; "
        f"app = create_app(); make_server('127.0.0.1', {port}, app.server, threaded=True).serve_forever()"
    )
    server_log_path = tmp_path / "e2e_server.log"
    server_log_file = server_log_path.open("w", encoding="utf-8", buffering=1)
    proc = subprocess.Popen(
        [sys.executable, "-c", srv_code],
        env=srv_env,
        stdout=server_log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            server_log_file.flush()
            err_out = server_log_path.read_text(encoding="utf-8", errors="replace")
            server_log_file.close()
            raise RuntimeError(f"Live test server exited prematurely ({proc.returncode}): {err_out}")
        try:
            with urllib.request.urlopen(f"{base_url}/login", timeout=1.0) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.15)
    else:
        proc.terminate()
        server_log_file.close()
        raise RuntimeError("Live test server did not become ready within 20s")

    shot_dir_env = os.getenv("RECON_E2E_SCREENSHOT_DIR")
    shot_dir = Path(shot_dir_env) if shot_dir_env else (tmp_path / "screenshots")
    shot_dir.mkdir(parents=True, exist_ok=True)

    try:
        yield {
            "base_url": base_url,
            "shot_dir": shot_dir,
            "server_log_path": server_log_path,
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        server_log_file.close()
        invalidate_catalog_cache()
        clear_perm_cache()


def _select_dmc_option(page: Page, input_selector: str, option_text: str) -> None:
    inp = page.locator(input_selector)
    if option_text in (inp.input_value() or ""):
        return
    inp.scroll_into_view_if_needed()
    inp.click()
    opts = page.locator(".mantine-Select-option:visible")
    if opts.count() == 0:
        page.wait_for_timeout(150)
        inp.press("ArrowDown")
    opt = page.locator(".mantine-Select-option:visible").filter(has_text=option_text).first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()


def test_model_center_and_studio_playwright_e2e(live_studio_server: dict[str, Any]) -> None:
    base_url = live_studio_server["base_url"]
    shot_dir: Path = live_studio_server["shot_dir"]
    server_log_path: Path = live_studio_server["server_log_path"]
    console_errors: list[str] = []
    page_errors: list[str] = []
    http_errors: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on(
            "response",
            lambda res: http_errors.append(f"{res.status} {res.url}") if res.status >= 400 else None,
        )

        # 1. Đăng nhập
        page.goto(f"{base_url}/login", wait_until="networkidle")
        page.locator("#login-username").fill("e2e_owner")
        page.locator("#login-password").fill("Owner@123456")
        page.locator("#login-submit-btn").click()
        try:
            page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
        except Exception as exc:
            alert_txt = (
                page.locator("#login-alert-container").inner_text()
                if page.locator("#login-alert-container").count()
                else "NONE"
            )
            srv_log = server_log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
            raise AssertionError(
                f"Login redirect timed out. url={page.url}, alert={alert_txt!r}, "
                f"console={console_errors}, http={http_errors}, server_log=\n{srv_log}"
            ) from exc

        # 2. Mở Model Center (/report-models) và tạo model mới
        page.goto(f"{base_url}/report-models", wait_until="networkidle")
        page.wait_for_selector("#rm-center-create-btn", timeout=15000)
        page.locator("#rm-center-create-btn").click()
        page.wait_for_selector("#rm-center-create-code", timeout=10000)
        page.locator("#rm-center-create-code").fill("E2E_SALES_MODEL")
        page.locator("#rm-center-create-name").fill("Mô hình E2E Doanh Thu")
        if "SRC_E2E_SQLITE" not in (page.locator("#rm-center-create-ds").input_value() or ""):
            _select_dmc_option(page, "#rm-center-create-ds", "SRC_E2E_SQLITE")
        page.locator("#rm-center-create-submit").click()

        try:
            page.wait_for_selector("#rms-page", timeout=15000)
        except Exception as exc:
            page.screenshot(path=str(shot_dir / "failure_debug.png"))
            alert_txt = (
                page.locator("#rm-center-create-alert").inner_text()
                if page.locator("#rm-center-create-alert").count()
                else "NONE"
            )
            raise AssertionError(
                f"Did not reach #rms-page. url={page.url}, alert={alert_txt!r}, console={console_errors}, http={http_errors}"
            ) from exc
        studio_url = page.url.split("?")[0]
        assert "/report-models/" in studio_url and not studio_url.rstrip("/").endswith("/report-models")

        # Kiểm tra /report-models/<id>/edit redirect sang /report-models/<id>
        page.goto(f"{studio_url}/edit", wait_until="networkidle")
        page.wait_for_selector("#rms-page", timeout=10000)
        assert page.url.rstrip("/") == studio_url.rstrip("/")

        # 3. Thêm bảng FACT_SALES & DIM_CUSTOMER từ Source Picker Drawer
        page.wait_for_selector("#rms-add-table-btn", timeout=15000)
        page.locator("#rms-add-table-btn").click()
        page.wait_for_selector("button[aria-label='Thêm bảng FACT_SALES vào mô hình']", timeout=15000)
        page.locator("button[aria-label='Thêm bảng FACT_SALES vào mô hình']").click()
        page.wait_for_function("() => document.querySelectorAll('.rms-entity-card').length === 1", timeout=10000)
        page.wait_for_selector("button[aria-label='Thêm bảng DIM_CUSTOMER vào mô hình']", timeout=10000)
        page.locator("button[aria-label='Thêm bảng DIM_CUSTOMER vào mô hình']").click()
        page.wait_for_function("() => document.querySelectorAll('.rms-entity-card').length === 2", timeout=10000)
        # Đóng drawer qua nút Đóng và chờ overlay ẩn hoàn toàn
        page.locator("#rms-picker-close-btn").click()
        page.wait_for_function(
            "() => [...document.querySelectorAll('.mantine-Drawer-overlay')].every(e => getComputedStyle(e).display === 'none')",
            timeout=5000,
        )
        page.wait_for_timeout(250)

        # 4. Cấu hình Table Role / Grain cho FACT_SALES + DIM_CUSTOMER + tạo quan hệ qua modal
        page.wait_for_selector(".rms-entity-card", timeout=10000)
        assert page.locator(".rms-entity-card").count() == 2

        page.locator("button[aria-label='Bảng FACT_SALES']").click()
        page.wait_for_selector("#rms-prop-tbl-role", timeout=10000)
        _select_dmc_option(page, "#rms-prop-tbl-role", "Fact (Bảng sự kiện)")
        page.locator("#rms-prop-tbl-grain-desc").fill("1 dòng = 1 hóa đơn")
        # Chọn SALES_ID cho Grain Keys
        page.locator("#rms-prop-tbl-grain-keys").click()
        grain_opt = page.locator(".mantine-MultiSelect-option:visible").filter(has_text="SALES_ID").first
        grain_opt.wait_for(state="visible", timeout=5000)
        grain_opt.click()
        page.keyboard.press("Escape")
        page.locator("#rms-prop-tbl-save").scroll_into_view_if_needed()
        page.locator("#rms-prop-tbl-save").click()
        page.wait_for_selector("#rms-status-bar:has-text('1F / 1D')", timeout=10000)

        page.locator("button[aria-label='Bảng DIM_CUSTOMER']").click()
        page.wait_for_selector("#rms-prop-tbl-role", timeout=10000)
        _select_dmc_option(page, "#rms-prop-tbl-role", "Dimension (Bảng chiều)")
        page.locator("#rms-prop-tbl-save").scroll_into_view_if_needed()
        page.locator("#rms-prop-tbl-save").click()
        page.wait_for_selector("#rms-status-bar:has-text('1F / 1D')", timeout=10000)

        # Tạo quan hệ FACT_SALES.CUSTOMER_ID -> DIM_CUSTOMER.CUSTOMER_ID qua modal
        page.locator("#rms-new-rel-btn").click()
        page.wait_for_selector("#rms-rel-m-name", timeout=10000)
        page.locator("#rms-rel-m-name").fill("REL_SALES_CUSTOMER")
        if "FACT_SALES" not in (page.locator("#rms-rel-m-from-tbl").input_value() or ""):
            _select_dmc_option(page, "#rms-rel-m-from-tbl", "FACT_SALES")
            page.wait_for_timeout(250)
        _select_dmc_option(page, "#rms-rel-m-from-col", "CUSTOMER_ID")
        if "DIM_CUSTOMER" not in (page.locator("#rms-rel-m-to-tbl").input_value() or ""):
            _select_dmc_option(page, "#rms-rel-m-to-tbl", "DIM_CUSTOMER")
            page.wait_for_timeout(250)
        _select_dmc_option(page, "#rms-rel-m-to-col", "CUSTOMER_ID")
        page.locator("#rms-rel-m-submit").click()
        page.wait_for_selector(".rms-rel-chip", timeout=10000)

        # 5. Auto Layout Star Schema & Fit canvas sau khi đã gắn vai trò Fact/Dim
        page.locator("#rms-auto-layout-btn").click()
        page.wait_for_selector("#rms-save-btn:has-text('Lưu nháp*')", timeout=10000)
        page.locator("#rms-zoom-fit-btn").click()
        page.wait_for_timeout(300)

        # Thêm Simple Measure TOTAL_REV từ nút "+ Measure" trên bảng FACT_SALES
        page.locator("button[aria-label='Bảng FACT_SALES']").click()
        page.wait_for_selector("#rms-prop-tbl-new-meas", timeout=10000)
        page.locator("#rms-prop-tbl-new-meas").click()
        page.wait_for_selector("#rms-prop-meas-code", timeout=10000)
        page.locator("#rms-prop-meas-code").fill("TOTAL_REV")
        page.locator("#rms-prop-meas-name").fill("Tổng doanh thu")
        _select_dmc_option(page, "#rms-prop-meas-base-fld", "AMOUNT")
        page.locator("#rms-prop-meas-save").click()
        page.wait_for_selector("#rms-status-bar:has-text('Measures: 1')", timeout=10000)

        # 6. Kéo nhẹ card trên canvas (vẫn tách biệt rõ ràng) và Lưu nháp
        header_box = page.locator(".rms-entity-header[data-drag-handle]").first.bounding_box()
        assert header_box is not None
        page.mouse.move(header_box["x"] + 30, header_box["y"] + 12)
        page.mouse.down()
        page.mouse.move(header_box["x"] + 50, header_box["y"] + 32, steps=6)
        page.mouse.up()
        page.wait_for_timeout(300)
        page.locator("#rms-save-btn").click()
        page.wait_for_selector("#rms-status-bar:has-text('Đã đồng bộ')", timeout=10000)

        # 7. Kiểm tra model (Validation Drawer aria-live="polite")
        page.locator("#rms-validate-btn").click()
        page.wait_for_selector("#rms-validate-live[aria-live='polite']", timeout=10000)
        page.wait_for_timeout(350)
        page.screenshot(path=str(shot_dir / "studio_validation_drawer.png"))
        page.keyboard.press("Escape")
        page.wait_for_function(
            "() => [...document.querySelectorAll('.mantine-Drawer-overlay')].every(e => getComputedStyle(e).display === 'none')",
            timeout=5000,
        )
        page.wait_for_timeout(250)

        # 8. Phát hành với Change Note -> chuyển sang ACTIVE chỉ đọc
        page.locator("#rms-publish-btn").click()
        page.wait_for_selector("#rms-pub-change-note", timeout=10000)
        page.locator("#rms-pub-change-note").fill("Phát hành E2E v1")
        page.locator("#rms-pub-confirm-btn").click()
        page.wait_for_selector("#rms-new-draft-btn", timeout=15000)
        page.wait_for_selector("#rms-publish-modal", state="hidden", timeout=5000)
        page.wait_for_timeout(350)
        assert page.locator("#rms-save-btn").is_disabled()
        assert page.locator("#rms-publish-btn").is_disabled()

        # Kiểm tra 1440×900 Light mode không tràn viewport
        overflow_1440 = page.evaluate(
            "() => ({sw: document.documentElement.scrollWidth, iw: window.innerWidth, "
            "sh: document.documentElement.scrollHeight, ih: window.innerHeight})"
        )
        assert overflow_1440["sw"] <= overflow_1440["iw"]
        assert overflow_1440["sh"] <= overflow_1440["ih"]
        page.screenshot(path=str(shot_dir / "studio_light_1440.png"))

        # 9. Bật Dark mode tại 1440×900
        page.locator("#app-color-scheme-toggle").click()
        page.wait_for_function(
            "() => document.documentElement.getAttribute('data-mantine-color-scheme') === 'dark'",
            timeout=5000,
        )
        page.screenshot(path=str(shot_dir / "studio_dark_1440.png"))

        # 10. Kiểm tra 1366×768
        page.set_viewport_size({"width": 1366, "height": 768})
        page.wait_for_timeout(300)
        overflow_1366 = page.evaluate(
            "() => ({sw: document.documentElement.scrollWidth, iw: window.innerWidth, "
            "sh: document.documentElement.scrollHeight, ih: window.innerHeight})"
        )
        assert overflow_1366["sw"] <= overflow_1366["iw"]
        assert overflow_1366["sh"] <= overflow_1366["ih"]
        page.screenshot(path=str(shot_dir / "studio_1366.png"))

        # 11. Kiểm tra chế độ < 900px (850×844 và Mobile 390×844: read-only notice, ẩn canvas, không tràn ngang)
        page.set_viewport_size({"width": 850, "height": 844})
        page.wait_for_timeout(250)
        assert page.locator(".rms-mobile-notice").is_visible()
        assert not page.locator("#rms-canvas-wrap").is_visible()
        page.screenshot(path=str(shot_dir / "studio_tablet_850.png"))

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(300)
        assert page.locator(".rms-mobile-notice").is_visible()
        assert not page.locator("#rms-canvas-wrap").is_visible()
        overflow_mobile = page.evaluate(
            "() => ({sw: document.documentElement.scrollWidth, iw: window.innerWidth})"
        )
        assert overflow_mobile["sw"] <= overflow_mobile["iw"]
        page.screenshot(path=str(shot_dir / "studio_mobile_390.png"))

        browser.close()

    assert not console_errors, f"Console errors: {console_errors}"
    assert not page_errors, f"Page errors: {page_errors}"
    assert not http_errors, f"HTTP errors >= 400: {http_errors}"
