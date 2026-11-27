"""Playwright E2E cho Report Studio Viewer (task 109 Bước 6).

Luồng đầy đủ trong trình duyệt Chromium thật:
- /report-models: tạo model E2E_SALES_MODEL (FACT_SALES + DIM_CUSTOMER,
  quan hệ, measure TOTAL_REV) rồi phát hành ACTIVE (tái dùng luồng đã
  chứng minh ở tests/e2e/test_model_studio_e2e.py).
- /report-studio: tạo báo cáo E2E_RPT_SALES, thêm 3 visual (Bar + Table +
  KPI) bằng nút + / Nhân bản / đổi loại visual, xem trước, lưu nháp,
  kiểm tra, phát hành.
- Chèn tham số P_CUST (LIKE_PREFIX trên CUSTOMER_NAME) trực tiếp vào DB
  (đường tạo param đã có unit test riêng; ở đây chỉ cần param để kiểm
  chứng lọc ở Viewer) rồi mở /reports/<id>: lọc "Cong ty A", xem đa
  visual, xuất 1 visual XLSX + 1 visual CSV qua worker thật.
- Kiểm tra Desktop 1366×768 & 1440×900 (Light + Dark, không cuộn trang),
  Mobile 390×844 (Viewer xem được, Studio báo giới hạn), /data-model
  có RECON_RPT_VISUAL*, zero console/page/HTTP error, chụp ảnh kiểm chứng.

Nhiễu mạng biết trước: DashIconify fetch icon từ CDN ngoài
(api.iconify.design / api.simplesvg.com / api.unisvg.com) mà VM không ra
được internet -> console lỗi ERR_TUNNEL_CONNECTION_FAILED xuất hiện cả
ở trang login, không phải do code mới (đã ghi ở Bước 4). Các lỗi này
được lọc khỏi danh sách console errors.
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
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from sqlalchemy import create_engine, text

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_data_source, recon_user
from app.engine.catalog import invalidate_catalog_cache
from app.services.perm import clear_perm_cache

# Console error do icon CDN ngoài không tới được — nhiễu môi trường, lọc ra.
_CONSOLE_NOISE = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "api.iconify.design",
    "api.simplesvg.com",
    "api.unisvg.com",
)


def _is_noise(msg: str) -> bool:
    return any(token in msg for token in _CONSOLE_NOISE)


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
def live_report_studio_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    invalidate_user_session_cache()
    invalidate_catalog_cache()
    clear_perm_cache()

    app_db = tmp_path / "e2e_report_studio_app.db"
    src_db = tmp_path / "e2e_report_studio_src.db"
    storage_dir = tmp_path / "storage"
    _seed_source_db(src_db)

    db_url = f"sqlite:///{app_db.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-report-studio-playwright-secret")
    monkeypatch.setenv("RECON_STORAGE_DIR", str(storage_dir))
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
                FULL_NAME="E2E Report Owner",
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
    srv_env["FLASK_SECRET_KEY"] = "test-report-studio-playwright-secret"
    srv_env["RECON_STORAGE_DIR"] = str(storage_dir)
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
    worker_log_path = tmp_path / "e2e_worker.log"
    worker_log_file = worker_log_path.open("w", encoding="utf-8", buffering=1)
    worker_holder: dict[str, Any] = {"proc": None}

    def start_worker() -> None:
        """Khởi động worker thật (chỉ cần cho bước xuất file).

        Không chạy từ đầu test: VM chỉ 1.5 CPU, worker poll DB mỗi 2s
        gây tranh CPU/khóa SQLite làm các callback UI chậm bất thường.
        """
        if worker_holder["proc"] is not None:
            return
        worker_holder["proc"] = subprocess.Popen(
            [sys.executable, "-m", "worker"],
            env=srv_env,
            stdout=worker_log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        time.sleep(1.0)
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
            "worker_log_path": worker_log_path,
            "app_db": app_db,
            "start_worker": start_worker,
        }
    finally:
        proc.terminate()
        worker_proc = worker_holder["proc"]
        if worker_proc is not None:
            worker_proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        if worker_proc is not None:
            try:
                worker_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker_proc.kill()
                worker_proc.wait(timeout=3)
        server_log_file.close()
        worker_log_file.close()
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


def _insert_viewer_param(app_db: Path) -> int:
    """Chèn param P_CUST (LIKE_PREFIX trên CUSTOMER_NAME) vào version ACTIVE.

    Trả report id để mở /reports/<id>.
    """
    eng = create_engine(f"sqlite:///{app_db.as_posix()}")
    with eng.begin() as conn:
        row = conn.execute(
            text(
                "SELECT t.REPORT_ID AS report_id, v.ID AS version_id "
                "FROM RECON_REPORT_TEMPLATE t "
                "JOIN RECON_RPT_TPL_VER v ON v.TEMPLATE_ID = t.ID "
                "JOIN RECON_REPORT r ON r.ID = t.REPORT_ID "
                "WHERE r.CODE = 'E2E_RPT_SALES' AND v.STATUS = 'ACTIVE'"
            )
        ).mappings().first()
        assert row is not None, "Không tìm thấy version ACTIVE của E2E_RPT_SALES"
        conn.execute(
            text(
                "INSERT INTO RECON_RPT_PARAM "
                "(VERSION_ID, CODE, LABEL, DATA_TYPE, CONTROL_TYPE, REQUIRED, "
                " DEFAULT_TYPE, DISPLAY_ROW, DISPLAY_ORDER, GRID_SPAN, "
                " FILTER_COLUMN, FILTER_OPERATOR, IS_VISIBLE) "
                "VALUES (:vid, 'P_CUST', 'Khách hàng', 'STRING', 'TEXT', 'N', "
                " 'NONE', 1, 10, 6, 'CUSTOMER_NAME', 'LIKE_PREFIX', 'Y')"
            ),
            {"vid": int(row["version_id"])},
        )
        report_id = int(row["report_id"])
    eng.dispose()
    return report_id



def _select_visual(page: Page, code: str, title: str, shot_dir: Path | None = None) -> None:
    """Bấm card visual theo mã rồi đợi panel phải hiện đúng tiêu đề.

    Click theo data-visual-code (không click giữa card vì điểm giữa có
    thể rơi vào nút hành động trong card), đồng bộ bằng giá trị ô tiêu
    đề để chắc chắn selection đã áp trước khi đổi loại/tiêu đề.
    """
    card = page.locator(f".rs-visual-card-body[data-visual-code='{code}']")
    try:
        # Nới timeout: render 3 card dưới tải CPU nặng có thể chậm.
        card.click(timeout=30000)
    except Exception:
        diag = page.evaluate(
            """(code) => {
                const el = document.querySelector(`.rs-visual-card[data-visual-code='${code}']`);
                if (!el) return {found: false};
                const r = el.getBoundingClientRect();
                const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
                const chain = [];
                let node = document.elementFromPoint(cx, cy);
                while (node && chain.length < 6) {
                    chain.push(node.tagName + '#' + (node.id || '') + '.' + String(node.className).split(' ')[0]);
                    node = node.parentElement;
                }
                return {found: true, x: Math.round(r.x), y: Math.round(r.y),
                    w: Math.round(r.width), h: Math.round(r.height),
                    visible: !!(r.width && r.height) && getComputedStyle(el).visibility !== 'hidden',
                    hitChain: chain};
            }""",
            code,
        )
        print(f"DIAG select {code} failed: {diag}")
        if shot_dir is not None:
            page.screenshot(path=str(shot_dir / f"diag_select_{code}.png"))
        raise
    page.wait_for_function(
        """(t) => {
            const el = document.querySelector('#rs-set-title');
            return el && el.value === t;
        }""",
        arg=title,
        timeout=10000,
    )


def _overflow(page: Page) -> dict[str, int]:
    return dict(
        page.evaluate(
            "() => ({sw: document.documentElement.scrollWidth, iw: window.innerWidth, "
            "sh: document.documentElement.scrollHeight, ih: window.innerHeight})"
        )
    )


def test_report_studio_playwright_e2e(live_report_studio_server: dict[str, Any]) -> None:
    base_url = live_report_studio_server["base_url"]
    shot_dir: Path = live_report_studio_server["shot_dir"]
    server_log_path: Path = live_report_studio_server["server_log_path"]
    app_db: Path = live_report_studio_server["app_db"]
    console_errors: list[str] = []
    page_errors: list[str] = []
    http_errors: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" and not _is_noise(msg.text) else None)
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

        # 2. /report-models: tạo model mới (luồng đã chứng minh ở test 107)
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
            page.screenshot(path=str(shot_dir / "failure_model_create.png"))
            alert_txt = (
                page.locator("#rm-center-create-alert").inner_text()
                if page.locator("#rm-center-create-alert").count()
                else "NONE"
            )
            raise AssertionError(
                f"Did not reach #rms-page. url={page.url}, alert={alert_txt!r}, console={console_errors}, http={http_errors}"
            ) from exc

        # 3. Thêm bảng FACT_SALES & DIM_CUSTOMER
        page.wait_for_selector("#rms-add-table-btn", timeout=15000)
        page.locator("#rms-add-table-btn").click()
        page.wait_for_selector("button[aria-label='Thêm bảng FACT_SALES vào mô hình']", timeout=15000)
        page.locator("button[aria-label='Thêm bảng FACT_SALES vào mô hình']").click()
        page.wait_for_function("() => document.querySelectorAll('.rms-entity-card').length === 1", timeout=10000)
        page.wait_for_selector("button[aria-label='Thêm bảng DIM_CUSTOMER vào mô hình']", timeout=10000)
        page.locator("button[aria-label='Thêm bảng DIM_CUSTOMER vào mô hình']").click()
        page.wait_for_function("() => document.querySelectorAll('.rms-entity-card').length === 2", timeout=10000)
        page.locator("#rms-picker-close-btn").click()
        page.wait_for_function(
            "() => [...document.querySelectorAll('.mantine-Drawer-overlay')].every(e => getComputedStyle(e).display === 'none')",
            timeout=5000,
        )
        page.wait_for_timeout(250)

        # 4. Gắn vai trò Fact/Dimension + quan hệ + measure TOTAL_REV
        page.locator("button[aria-label='Bảng FACT_SALES']").click()
        page.wait_for_selector("#rms-prop-tbl-role", timeout=10000)
        _select_dmc_option(page, "#rms-prop-tbl-role", "Fact (Bảng sự kiện)")
        page.locator("#rms-prop-tbl-grain-desc").fill("1 dòng = 1 hóa đơn")
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

        page.locator("#rms-new-rel-btn").click()
        # Click có thể rơi mất khi trang đang vẽ lại sau khi lưu role
        # (chỉ gặp khi chạy sau test 107: log server không thấy request
        # nào từ click dù nút đã bấm được) — bấm lại 1 lần nếu modal
        # chưa mở sau 5s; nếu nút thật sự hỏng thì wait 30s sau vẫn fail.
        try:
            page.wait_for_selector("#rms-rel-m-name", timeout=5000)
        except PlaywrightTimeoutError:
            page.locator("#rms-new-rel-btn").click()
            page.wait_for_selector("#rms-rel-m-name", timeout=30000)
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

        page.locator("button[aria-label='Bảng FACT_SALES']").click()
        page.wait_for_selector("#rms-prop-tbl-new-meas", timeout=10000)
        page.locator("#rms-prop-tbl-new-meas").click()
        page.wait_for_selector("#rms-prop-meas-code", timeout=10000)
        page.locator("#rms-prop-meas-code").fill("TOTAL_REV")
        page.locator("#rms-prop-meas-name").fill("Tổng doanh thu")
        _select_dmc_option(page, "#rms-prop-meas-base-fld", "AMOUNT")
        page.locator("#rms-prop-meas-save").click()
        page.wait_for_selector("#rms-status-bar:has-text('Measures: 1')", timeout=10000)

        # 5. Lưu nháp + phát hành model
        page.locator("#rms-save-btn").click()
        page.wait_for_selector("#rms-status-bar:has-text('Đã đồng bộ')", timeout=10000)
        page.locator("#rms-publish-btn").click()
        page.wait_for_selector("#rms-pub-change-note", timeout=10000)
        page.locator("#rms-pub-change-note").fill("Phát hành E2E v1")
        page.locator("#rms-pub-confirm-btn").click()
        page.wait_for_selector("#rms-new-draft-btn", timeout=15000)
        page.wait_for_selector("#rms-publish-modal", state="hidden", timeout=5000)
        page.wait_for_timeout(350)
        assert page.locator("#rms-save-btn").is_disabled()
        assert page.locator("#rms-publish-btn").is_disabled()

        # 6. /report-studio: tạo báo cáo mới
        page.goto(f"{base_url}/report-studio", wait_until="networkidle")
        page.wait_for_selector("#rs-center-create-btn", timeout=15000)
        page.locator("#rs-center-create-btn").click()
        page.wait_for_selector("#rs-center-create-code", timeout=10000)
        page.locator("#rs-center-create-code").fill("E2E_RPT_SALES")
        page.locator("#rs-center-create-name").fill("Báo cáo E2E Doanh Thu")
        if "E2E_SALES_MODEL" not in (page.locator("#rs-center-create-model").input_value() or ""):
            _select_dmc_option(page, "#rs-center-create-model", "E2E_SALES_MODEL")
        page.locator("#rs-center-create-submit").click()
        try:
            page.wait_for_selector("#rs-page", timeout=15000)
        except Exception as exc:
            page.screenshot(path=str(shot_dir / "failure_report_create.png"))
            alert_txt = (
                page.locator("#rs-center-create-alert").inner_text()
                if page.locator("#rs-center-create-alert").count()
                else "NONE"
            )
            raise AssertionError(
                f"Did not reach #rs-page. url={page.url}, alert={alert_txt!r}, console={console_errors}, http={http_errors}"
            ) from exc
        studio_url = page.url.split("?")[0]

        # 7. Thêm visual 1: TABLE (X=CUSTOMER_NAME, Y=TOTAL_REV) rồi đổi sang BAR
        page.wait_for_selector("button[aria-label='Thêm trường CUSTOMER_NAME vào visual']", timeout=15000)
        page.locator("button[aria-label='Thêm trường CUSTOMER_NAME vào visual']").click()
        page.wait_for_function("() => document.querySelectorAll('.rs-visual-card').length === 1", timeout=10000)
        _select_visual(page, "V_001", "Visual CUSTOMER_NAME", shot_dir)
        page.locator("button[aria-label='Thêm trường TOTAL_REV vào visual']").click()
        page.wait_for_function(
            "() => document.querySelector('#rs-canvas-body').innerText.includes('TOTAL_REV')",
            timeout=10000,
        )
        _select_dmc_option(page, "#rs-set-type", "BAR")
        page.wait_for_timeout(500)
        # Đổi TABLE -> BAR không rớt field nên không hiện modal xác nhận.
        # Lưu ý: DMC Modal không render element mang id gốc rs-type-confirm-modal;
        # body bên trong (rs-type-confirm-body) mới là dấu hiệu modal đang mở.
        assert page.locator("#rs-type-confirm-body").count() == 0
        page.locator("#rs-set-title").fill("Biểu đồ doanh thu")
        page.wait_for_timeout(400)

        # 8. Nhân bản V_001 -> V_002, đổi sang TABLE
        page.locator("button[aria-label='Nhân bản visual V_001']").click()
        page.wait_for_function("() => document.querySelectorAll('.rs-visual-card').length === 2", timeout=10000)
        _select_visual(page, "V_002", "Biểu đồ doanh thu (bản sao)", shot_dir)
        _select_dmc_option(page, "#rs-set-type", "TABLE")
        page.wait_for_timeout(500)
        page.locator("#rs-set-title").fill("Bảng doanh thu")
        page.wait_for_timeout(400)

        # 9. Nhân bản V_001 -> V_003, đổi sang KPI (rớt CUSTOMER_NAME -> modal xác nhận)
        page.locator("button[aria-label='Nhân bản visual V_001']").click()
        page.wait_for_function("() => document.querySelectorAll('.rs-visual-card').length === 3", timeout=10000)
        _select_visual(page, "V_003", "Biểu đồ doanh thu (bản sao)", shot_dir)
        _select_dmc_option(page, "#rs-set-type", "KPI")
        page.wait_for_selector("#rs-type-confirm-body", timeout=15000)
        assert "CUSTOMER_NAME" in page.locator("#rs-type-confirm-body").inner_text()
        page.locator("#rs-type-confirm-yes").click()
        page.wait_for_selector("#rs-type-confirm-body", state="hidden", timeout=5000)
        page.wait_for_timeout(400)
        page.locator("#rs-set-title").fill("Tổng doanh thu")
        page.wait_for_timeout(400)
        page.screenshot(path=str(shot_dir / "studio_design_1440.png"))

        # 10. Xem trước: Table hiện Cong ty A/B, KPI hiện tổng 400,000
        page.locator("#rs-preview-btn").click()
        page.wait_for_function(
            "() => document.querySelector('#rs-canvas-body').innerText.includes('Cong ty A')",
            timeout=15000,
        )
        page.wait_for_function(
            "() => document.querySelector('#rs-canvas-body').innerText.includes('400,000')",
            timeout=15000,
        )
        page.screenshot(path=str(shot_dir / "studio_preview_1440.png"))

        # Lọc xem trước: chỉ còn Cong ty A
        _select_dmc_option(page, "#rs-preview-filter-field", "Customer Name")
        page.locator("#rs-preview-filter-value").fill("Cong ty A")
        page.wait_for_function(
            "() => document.querySelector('#rs-canvas-body').innerText.includes('Cong ty A') "
            "&& !document.querySelector('#rs-canvas-body').innerText.includes('Cong ty B')",
            timeout=15000,
        )
        page.locator("#rs-preview-filter-clear").click()
        page.wait_for_function(
            "() => document.querySelector('#rs-canvas-body').innerText.includes('Cong ty B')",
            timeout=15000,
        )

        # 11. Quay lại thiết kế -> Lưu nháp -> Kiểm tra -> Phát hành
        page.locator("#rs-preview-btn").click()
        page.wait_for_function(
            "() => document.querySelectorAll('.rs-visual-card').length === 3",
            timeout=10000,
        )
        page.locator("#rs-save-btn").click()
        page.wait_for_selector("text=Đã lưu bản nháp", timeout=15000)
        page.locator("#rs-validate-btn").click()
        # DMC Drawer cũng không render id gốc (như Modal): body bên trong mới
        # là dấu hiệu drawer đang mở.
        page.wait_for_selector("#rs-validate-drawer-body", timeout=10000)
        page.wait_for_timeout(500)
        page.keyboard.press("Escape")
        page.wait_for_function(
            "() => [...document.querySelectorAll('.mantine-Drawer-overlay')].every(e => getComputedStyle(e).display === 'none')",
            timeout=5000,
        )
        page.locator("#rs-publish-btn").click()
        page.wait_for_selector("#rs-publish-note", timeout=10000)
        page.locator("#rs-publish-note").fill("Phát hành E2E v1")
        page.locator("#rs-publish-submit").click()
        page.wait_for_selector("#rs-new-draft-btn", timeout=15000)
        page.wait_for_selector("#rs-publish-modal", state="hidden", timeout=5000)
        page.wait_for_timeout(350)

        # 12. Chèn param lọc + mở Viewer
        report_id = _insert_viewer_param(app_db)
        page.goto(f"{base_url}/reports/{report_id}", wait_until="networkidle")
        page.wait_for_selector("#viewer-run-btn", timeout=15000)
        page.screenshot(path=str(shot_dir / "viewer_before_run_1440.png"))

        # 13. Lọc tham số P_CUST = "Cong ty A" rồi Xem báo cáo
        page.locator("input[placeholder*='Khách hàng'], input[aria-label*='Khách hàng']").first.fill("Cong ty A")
        page.locator("#viewer-run-btn").click()
        page.wait_for_function(
            "() => document.querySelector('#viewer-result-container').innerText.includes('Cong ty A')",
            timeout=20000,
        )
        page.wait_for_timeout(500)
        result_text = page.locator("#viewer-result-container").inner_text()
        assert "Cong ty B" not in result_text
        assert "150,000" in result_text
        page.screenshot(path=str(shot_dir / "viewer_filtered_1440.png"))

        # 14. Xuất XLSX visual Bảng (V_002) + CSV visual Biểu đồ (V_001) (qua worker thật)
        # Hook data-visual-code/data-export-format trên nút xuất (viewer): selector
        # theo Paper + has_text mơ hồ vì Paper ngoài cùng chứa cả 3 nút Xuất.
        live_report_studio_server["start_worker"]()
        with page.expect_download(timeout=60000) as dl_info:
            page.locator('button[data-visual-code="V_002"][data-export-format="XLSX"]').click()
        download = dl_info.value
        xlsx_path = shot_dir / "e2e_table_export.xlsx"
        download.save_as(str(xlsx_path))
        assert xlsx_path.stat().st_size > 0
        import openpyxl

        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws = wb.active
        assert ws is not None
        rows = list(ws.iter_rows(values_only=True))
        assert rows, "File XLSX rỗng"
        assert any("Cong ty A" in str(c) for r in rows for c in r if c is not None)
        assert any(c == 150000 for r in rows for c in r if isinstance(c, (int, float)))
        wb.close()

        bar_card = page.locator('button[data-visual-code="V_001"][data-export-format="CSV"]')
        with page.expect_download(timeout=60000) as dl_info2:
            bar_card.click()
        download2 = dl_info2.value
        csv_path = shot_dir / "e2e_bar_export.csv"
        download2.save_as(str(csv_path))
        csv_text = csv_path.read_text(encoding="utf-8-sig")
        assert "Cong ty A" in csv_text
        assert "150000" in csv_text

        # 15. Kiểm tra không tràn ở 1440×900 Light + Dark + 1366×768
        ov = _overflow(page)
        assert ov["sw"] <= ov["iw"], f"Tràn ngang 1440 Light: {ov}"
        assert ov["sh"] <= ov["ih"], f"Tràn dọc 1440 Light: {ov}"
        page.screenshot(path=str(shot_dir / "viewer_light_1440.png"))
        page.locator("#app-color-scheme-toggle").click()
        page.wait_for_function(
            "() => document.documentElement.getAttribute('data-mantine-color-scheme') === 'dark'",
            timeout=5000,
        )
        page.wait_for_timeout(400)
        ov_dark = _overflow(page)
        assert ov_dark["sw"] <= ov_dark["iw"], f"Tràn ngang 1440 Dark: {ov_dark}"
        assert ov_dark["sh"] <= ov_dark["ih"], f"Tràn dọc 1440 Dark: {ov_dark}"
        page.screenshot(path=str(shot_dir / "viewer_dark_1440.png"))
        page.locator("#app-color-scheme-toggle").click()
        page.wait_for_function(
            "() => document.documentElement.getAttribute('data-mantine-color-scheme') === 'light'",
            timeout=5000,
        )

        page.set_viewport_size({"width": 1366, "height": 768})
        page.wait_for_timeout(400)
        ov_1366 = _overflow(page)
        assert ov_1366["sw"] <= ov_1366["iw"], f"Tràn ngang 1366: {ov_1366}"
        assert ov_1366["sh"] <= ov_1366["ih"], f"Tràn dọc 1366: {ov_1366}"
        page.screenshot(path=str(shot_dir / "viewer_1366.png"))

        # 16. Mobile 390×844: Viewer xem được, không tràn ngang; Studio báo giới hạn
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(400)
        ov_mob = _overflow(page)
        assert ov_mob["sw"] <= ov_mob["iw"], f"Tràn ngang mobile Viewer: {ov_mob}"
        assert "Cong ty A" in page.locator("#viewer-result-container").inner_text()
        page.screenshot(path=str(shot_dir / "viewer_mobile_390.png"))

        page.goto(f"{studio_url}", wait_until="networkidle")
        page.wait_for_timeout(400)
        assert page.locator(".rs-mobile-notice").is_visible()
        ov_mob_studio = _overflow(page)
        assert ov_mob_studio["sw"] <= ov_mob_studio["iw"], f"Tràn ngang mobile Studio: {ov_mob_studio}"
        page.screenshot(path=str(shot_dir / "studio_mobile_390.png"))

        # 17. /data-model có bảng RECON_RPT_VISUAL*
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{base_url}/data-model", wait_until="networkidle")
        page.wait_for_timeout(1000)
        body_text = page.locator("body").inner_text()
        assert "RECON_RPT_VISUAL" in body_text
        assert "RECON_RPT_VISUAL_FIELD" in body_text
        page.screenshot(path=str(shot_dir / "data_model_1440.png"))

        browser.close()

    assert not console_errors, f"Console errors: {console_errors}"
    assert not page_errors, f"Page errors: {page_errors}"
    assert not http_errors, f"HTTP errors >= 400: {http_errors}"
