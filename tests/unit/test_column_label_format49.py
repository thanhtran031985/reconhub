"""Task 49: nhãn cột mặc định dạng Title Case (tab 4, page report-admin).

- Tên cột DB UPPER_SNAKE_CASE → nhãn Title Case (TRANSACTION_DATE →
  Transaction Date), áp cho mọi cột.
- Nhãn user đã sửa (khác tên cột) giữ nguyên.
- Cột mới khi apply diff nguồn được lưu nhãn đã đổi format ngay từ đầu.
"""

from __future__ import annotations

import pytest

from tests.unit.test_page_report_admin import _draft_state, _dump, _patch_describe
from tests.unit.test_report_run_execute import admin_ctx, run_env
from tests.unit.test_report_source_diff import diff_env

__all__ = ["run_env", "admin_ctx", "diff_env"]


class TestPrettify:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("TRANSACTION_DATE", "Transaction Date"),
            ("INVOICE_DATE", "Invoice Date"),
            ("ORG_CODE", "Org Code"),
            ("AMOUNT", "Amount"),
            ("CUSTOMER_NAME", "Customer Name"),
            ("A", "A"),
            ("COL_2", "Col 2"),
            ("", ""),
            ("ORDER__DATE", "Order Date"),
            ("_AMOUNT_", "Amount"),
            ("TXN_DATE", "Txn Date"),
        ],
    )
    def test_prettify_column_label(self, raw, expected):
        from app.services.report_source import prettify_column_label

        assert prettify_column_label(raw) == expected


def _fake_row(**overrides):
    row = {
        "ID": 1,
        "FIELD_NAME": "TRANSACTION_DATE",
        "LABEL": "TRANSACTION_DATE",
        "DATA_TYPE": "DATE",
        "DISPLAY_ORDER": 10,
        "WEB_VISIBLE": "Y",
        "EXCEL_VISIBLE": "Y",
        "FORMAT_MASK": None,
        "ALIGNMENT": "LEFT",
        "WIDTH": 180,
        "IS_TOTAL": "N",
    }
    row.update(overrides)
    return row


class TestEffectiveLabel:
    def test_column_dict_prettifies_untouched_default(self):
        """Nhãn còn bằng đúng tên cột → hiển thị Title Case."""
        from app.services.report_column import _column_dict

        assert _column_dict(_fake_row())["label"] == "Transaction Date"

    def test_column_dict_keeps_user_label(self):
        """Nhãn user đã sửa (khác tên cột) → giữ nguyên."""
        from app.services.report_column import _column_dict

        assert _column_dict(_fake_row(LABEL="Ngày giao dịch"))["label"] == "Ngày giao dịch"

    def test_column_dict_keeps_stored_prettified(self):
        """Nhãn đã lưu dạng Title Case → giữ nguyên, không đổi lại."""
        from app.services.report_column import _column_dict

        assert (
            _column_dict(_fake_row(LABEL="Transaction Date"))["label"]
            == "Transaction Date"
        )


class TestCreation:
    def test_apply_diff_stores_prettified_label(self, diff_env, admin_ctx):
        """Cột mới từ apply diff nguồn: LABEL lưu đã là Title Case."""
        from sqlalchemy import select

        from app.db.metadata import recon_rpt_column
        from app.services.report_source import apply_source_diff

        diff = {
            "added": [
                {
                    "name": "TRANSACTION_DATE",
                    "data_type": "DATE",
                    "oracle_data_type": "DATE",
                    "nullable": True,
                    "length": None,
                    "precision": None,
                    "scale": None,
                }
            ],
            "removed": [],
            "type_changed": [],
            "new_binds": [],
            "missing_binds": [],
        }
        res = apply_source_diff(admin_ctx, diff_env["view_version_id"], diff)
        assert res.ok, res.message
        engine = diff_env["engine"]
        with engine.connect() as conn:
            label = conn.execute(
                select(recon_rpt_column.c.LABEL).where(
                    recon_rpt_column.c.VERSION_ID == diff_env["view_version_id"],
                    recon_rpt_column.c.FIELD_NAME == "TRANSACTION_DATE",
                )
            ).scalar_one()
        assert label == "Transaction Date"


class TestUserLabelWins:
    def _draft_with_columns(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        state, alert = page.handle_analyze_sql(
            1,
            state,
            "SELECT amount, org, txn_date FROM fin_revenue WHERE org = :p_org",
        )
        assert state["analyzed"] is True, _dump(alert)
        return run_env["draft_version_id"]

    def test_grid_shows_prettified_then_keeps_user_label(
        self, run_env, admin_ctx, monkeypatch
    ):
        """Tab 4 hiện Title Case; user sửa nhãn → lưu → vẫn là nhãn user."""
        import app.ui.pages.report_admin as page
        from app.services.report_column import get_result_layout, list_columns

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        cols = list_columns(admin_ctx, vid).data
        by_field = {c["field_name"]: c for c in cols}
        assert by_field["AMOUNT"]["label"] == "Amount"
        assert by_field["ORG"]["label"] == "Org"
        assert by_field["TXN_DATE"]["label"] == "Txn Date"
        # Viewer/Export dùng chung nhãn hiệu dụng.
        layout = get_result_layout(admin_ctx, vid, "web")
        assert layout.ok
        assert {
            c["field_name"]: c["label"] for c in layout.data["columns"]
        }["TXN_DATE"] == "Txn Date"

        amount = by_field["AMOUNT"]
        ok, _alert = page.handle_column_save(
            1,
            _draft_state(run_env) | {"version_id": vid},
            rows=[{"id": amount["id"], "label": "Số tiền"}],
        )
        assert ok is True
        cols = list_columns(admin_ctx, vid).data
        by_field = {c["field_name"]: c for c in cols}
        assert by_field["AMOUNT"]["label"] == "Số tiền"
        assert by_field["TXN_DATE"]["label"] == "Txn Date"


class TestPreexistingEffectiveCollision:
    """Hồi quy tab 4: trùng nhãn hiệu dụng có sẵn từ trước không được chặn
    mọi lần Lưu cột (báo lỗi từ user 11/11/2026: sửa nhãn rồi lưu vẫn về cũ)."""

    def _draft_with_columns(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        state, alert = page.handle_analyze_sql(
            1,
            state,
            "SELECT amount, org, txn_date FROM fin_revenue WHERE org = :p_org",
        )
        assert state["analyzed"] is True, _dump(alert)
        return run_env["draft_version_id"]

    def _grid_rows(self, cols, changed_field=None, changed_label=None):
        keys = (
            "id",
            "label",
            "format_mask",
            "alignment",
            "width",
            "web_visible",
            "excel_visible",
            "is_total",
        )
        rows = []
        for c in cols:
            row = {k: c[k] for k in keys}
            if c["field_name"] == changed_field:
                row["label"] = changed_label
            rows.append(row)
        return rows

    def test_bulk_save_with_preexisting_collision_succeeds(
        self, run_env, admin_ctx, monkeypatch
    ):
        """TXN_DATE đã có nhãn 'Transaction Date' (user đặt tay) + cột
        TRANSACTION_DATE mới (nhãn thô → hiệu dụng cùng 'Transaction Date'):
        sửa 1 nhãn không liên quan vẫn lưu được."""
        from sqlalchemy import update as sa_update

        from app.db.metadata import recon_rpt_column
        from app.services.report_column import list_columns, update_columns

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        engine = run_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                sa_update(recon_rpt_column)
                .where(
                    recon_rpt_column.c.VERSION_ID == vid,
                    recon_rpt_column.c.FIELD_NAME == "TXN_DATE",
                )
                .values(LABEL="Transaction Date")
            )
            conn.execute(
                recon_rpt_column.insert().values(
                    VERSION_ID=vid,
                    FIELD_NAME="TRANSACTION_DATE",
                    LABEL="TRANSACTION_DATE",
                    DATA_TYPE="DATE",
                    DISPLAY_ORDER=40,
                    WEB_VISIBLE="Y",
                    EXCEL_VISIBLE="Y",
                    ALIGNMENT="LEFT",
                    WIDTH=180,
                    IS_TOTAL="N",
                )
            )
        cols = list_columns(admin_ctx, vid).data
        rows = self._grid_rows(cols, "AMOUNT", "Số tiền")
        res = update_columns(admin_ctx, vid, rows)
        assert res.ok, res.message
        cols = list_columns(admin_ctx, vid).data
        assert next(c for c in cols if c["field_name"] == "AMOUNT")["label"] == "Số tiền"

    def test_bulk_save_creating_new_duplicate_allowed(
        self, run_env, admin_ctx, monkeypatch
    ):
        """Đổi nhãn thành giá trị trùng nhãn hiệu dụng của cột khác thì vẫn
        lưu được (task 50: bỏ chặn trùng nhãn theo yêu cầu user)."""
        from app.services.report_column import list_columns, update_columns

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        cols = list_columns(admin_ctx, vid).data
        rows = self._grid_rows(cols, "AMOUNT", "Txn Date")
        res = update_columns(admin_ctx, vid, rows)
        assert res.ok, res.message
        cols = list_columns(admin_ctx, vid).data
        assert next(c for c in cols if c["field_name"] == "AMOUNT")["label"] == "Txn Date"
