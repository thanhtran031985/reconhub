"""Tests cho Task 95: Đồng bộ nhãn cột từ lookup DB_COLUMN_MAPPING khi tạo template và migrate fact_bill."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.context import Ctx, Role
from app.db.engine import get_recon_engine
from app.db.metadata import recon_lookup_code, recon_lookup_type, recon_rpt_column
from app.services.lookup import get_db_column_mappings, migrate_fact_bill_columns
from tests.unit.test_report_source_diff import diff_env

__all__ = ["diff_env"]


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", role=Role.ADMIN)


class TestStep1MigrateFactBill:
    def test_migrate_fact_bill_populates_119_columns(self):
        """Bước 1: migrate các field của fact_bill vào DB_COLUMN_MAPPING đủ 119 cột, không trùng lặp."""
        engine = get_recon_engine()
        with engine.begin() as conn:
            migrate_fact_bill_columns(conn)

        with engine.connect() as conn:
            # Kiểm tra loại danh mục DB_COLUMN_MAPPING tồn tại
            type_row = conn.execute(
                select(recon_lookup_type).where(recon_lookup_type.c.LOOKUP_TYPE == "DB_COLUMN_MAPPING")
            ).mappings().first()
            assert type_row is not None
            assert type_row["IS_ACTIVE"] == "Y"

            # Kiểm tra số lượng mã trong DB_COLUMN_MAPPING phải đúng 119
            rows = conn.execute(
                select(recon_lookup_code).where(recon_lookup_code.c.LOOKUP_TYPE == "DB_COLUMN_MAPPING")
            ).mappings().all()
            codes = {r["LOOKUP_CODE"].upper(): r for r in rows}
            assert len(codes) == 119, f"Kỳ vọng 119 cột nhưng có {len(codes)} cột"

            # 7 mã ban đầu phải được giữ nguyên
            for original in ("CONFIRM_DATE", "CONT_NO", "CONT_SIZE", "CONT_TYPE", "INVOICE_DATE", "INVOICE_NO", "INV_CURRENCY"):
                assert original in codes

            # Các mã mới phải có mặt
            assert "TRANSACTION_DATE" in codes
            assert "INVOICE_STATUS" in codes
            assert "TOTAL_AMOUNT" in codes
            assert "BILL_CREATED_BY" in codes

            # Chạy lại lần nữa (idempotent) không được thêm cột nào
            with engine.begin() as conn2:
                added_again = migrate_fact_bill_columns(conn2)
            assert added_again == 0


class TestStep2InitialMappingOnCreate:
    def test_apply_diff_uses_lookup_mapping_on_create(self, diff_env, admin_ctx):
        """Bước 2: Khi tạo template mới / discover cột lần đầu, nhãn mặc định lấy từ DB_COLUMN_MAPPING."""
        from app.services.report_source import apply_source_diff

        eng = diff_env["engine"]
        with eng.begin() as conn:
            migrate_fact_bill_columns(conn)

        diff = {
            "added": [
                {
                    "name": "CONT_NO",
                    "data_type": "STRING",
                    "oracle_data_type": "VARCHAR2",
                    "nullable": True,
                    "length": 50,
                    "precision": None,
                    "scale": None,
                },
                {
                    "name": "TRANSACTION_DATE",
                    "data_type": "DATE",
                    "oracle_data_type": "DATE",
                    "nullable": True,
                    "length": None,
                    "precision": None,
                    "scale": None,
                },
                {
                    "name": "UNKNOWN_CUSTOM_COL",
                    "data_type": "STRING",
                    "oracle_data_type": "VARCHAR2",
                    "nullable": True,
                    "length": 50,
                    "precision": None,
                    "scale": None,
                },
            ],
            "removed": [],
            "type_changed": [],
            "new_binds": [],
            "missing_binds": [],
        }

        version_id = diff_env["view_version_id"]
        res = apply_source_diff(admin_ctx, version_id, diff)
        assert res.ok

        with eng.connect() as conn:
            cols = conn.execute(
                select(recon_rpt_column).where(recon_rpt_column.c.VERSION_ID == version_id)
            ).mappings().all()
            by_name = {c["FIELD_NAME"]: c for c in cols}

            # CONT_NO có trong lookup -> lấy nhãn từ lookup
            assert by_name["CONT_NO"]["LABEL"] == "Số container"
            # TRANSACTION_DATE có trong lookup -> lấy nhãn từ lookup
            assert by_name["TRANSACTION_DATE"]["LABEL"] == "Ngày PS"
            # UNKNOWN_CUSTOM_COL không có trong lookup -> fallback Title Case
            assert by_name["UNKNOWN_CUSTOM_COL"]["LABEL"] == "Unknown Custom Col"

    def test_lookup_mapping_case_insensitive(self):
        """So sánh mã lookup không phân biệt hoa thường."""
        mappings = get_db_column_mappings()
        assert mappings.get("CONT_NO") == "Số container"
        assert mappings.get("cont_no".upper()) == "Số container"

    def test_inactive_lookup_code_ignored(self, diff_env, admin_ctx, monkeypatch):
        """Mã lookup bị vô hiệu hóa (IS_ACTIVE='N') không được dùng, fallback về Title Case."""
        from app.services.lookup import _clear_cache
        from app.services.report_source import apply_source_diff

        eng = diff_env["engine"]
        monkeypatch.setattr("app.services.report_column.get_recon_engine", lambda: eng)
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: eng)
        with eng.begin() as conn:
            migrate_fact_bill_columns(conn)
            # Vô hiệu hóa mã CONT_NO
            conn.execute(
                recon_lookup_code.update()
                .where(
                    recon_lookup_code.c.LOOKUP_TYPE == "DB_COLUMN_MAPPING",
                    recon_lookup_code.c.LOOKUP_CODE == "CONT_NO",
                )
                .values(IS_ACTIVE="N")
            )
        _clear_cache()

        diff = {
            "added": [
                {
                    "name": "CONT_NO",
                    "data_type": "STRING",
                    "oracle_data_type": "VARCHAR2",
                    "nullable": True,
                    "length": 50,
                    "precision": None,
                    "scale": None,
                }
            ],
            "removed": [],
            "type_changed": [],
            "new_binds": [],
            "missing_binds": [],
        }
        version_id = diff_env["view_version_id"]
        res = apply_source_diff(admin_ctx, version_id, diff)
        assert res.ok

        with eng.connect() as conn:
            label = conn.scalar(
                select(recon_rpt_column.c.LABEL).where(
                    recon_rpt_column.c.VERSION_ID == version_id,
                    recon_rpt_column.c.FIELD_NAME == "CONT_NO",
                )
            )
            # Vì CONT_NO đã bị inactive -> fallback về Title Case "Cont No"
            assert label == "Cont No"


class TestStep3PreserveUserInputOnEdit:
    def test_open_edit_preserves_user_entered_label(self, diff_env, admin_ctx, monkeypatch):
        """Bước 3: Khi mở lại hoặc edit, nhãn đã được người dùng chỉnh sửa KHÔNG bị đè bởi lookup."""
        from app.services.report_column import list_columns, update_columns
        from app.services.report_source import apply_source_diff

        eng = diff_env["engine"]
        monkeypatch.setattr("app.services.report_column.get_recon_engine", lambda: eng)
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: eng)
        with eng.begin() as conn:
            migrate_fact_bill_columns(conn)

        diff = {
            "added": [
                {
                    "name": "CONT_NO",
                    "data_type": "STRING",
                    "oracle_data_type": "VARCHAR2",
                    "nullable": True,
                    "length": 50,
                    "precision": None,
                    "scale": None,
                }
            ],
            "removed": [],
            "type_changed": [],
            "new_binds": [],
            "missing_binds": [],
        }
        version_id = diff_env["view_version_id"]
        apply_source_diff(admin_ctx, version_id, diff)

        # Lấy danh sách cột
        cols_res = list_columns(admin_ctx, version_id)
        assert cols_res.ok
        cont_col = next(c for c in cols_res.data if c["field_name"] == "CONT_NO")
        col_id = cont_col["id"]

        # Người dùng sửa nhãn thủ công trên Tab 4 thành nhãn riêng
        custom_label = "Mã số Container Riêng"
        update_res = update_columns(
            admin_ctx,
            version_id,
            [
                {
                    "id": col_id,
                    "label": custom_label,
                }
            ],
        )
        assert update_res.ok

        # Khi load lại / mở lại template để edit: nhãn phải là nhãn do user đã sửa, không bị đè về "Số container"
        reload_res = list_columns(admin_ctx, version_id)
        assert reload_res.ok
        reloaded_cont = next(c for c in reload_res.data if c["field_name"] == "CONT_NO")
        assert reloaded_cont["label"] == custom_label

        with eng.connect() as conn:
            saved_label = conn.scalar(
                select(recon_rpt_column.c.LABEL).where(recon_rpt_column.c.ID == col_id)
            )
            assert saved_label == custom_label

    def test_lookup_change_does_not_override_saved_template(self, diff_env, admin_ctx, monkeypatch):
        """Thay đổi nhãn trong /lookups sau khi template đã lưu không ghi đè nhãn của template."""
        from app.services.lookup import _clear_cache
        from app.services.report_column import list_columns
        from app.services.report_source import apply_source_diff

        eng = diff_env["engine"]
        monkeypatch.setattr("app.services.report_column.get_recon_engine", lambda: eng)
        monkeypatch.setattr("app.services.lookup.get_recon_engine", lambda: eng)
        with eng.begin() as conn:
            migrate_fact_bill_columns(conn)

        diff = {
            "added": [
                {
                    "name": "CONT_NO",
                    "data_type": "STRING",
                    "oracle_data_type": "VARCHAR2",
                    "nullable": True,
                    "length": 50,
                    "precision": None,
                    "scale": None,
                }
            ],
            "removed": [],
            "type_changed": [],
            "new_binds": [],
            "missing_binds": [],
        }
        version_id = diff_env["view_version_id"]
        apply_source_diff(admin_ctx, version_id, diff)

        # Ban đầu CONT_NO lưu "Số container"
        cols_before = list_columns(admin_ctx, version_id)
        cont_before = next(c for c in cols_before.data if c["field_name"] == "CONT_NO")
        assert cont_before["label"] == "Số container"

        # Admin vào /lookups đổi CONT_NO thành "Thùng Container To"
        with eng.begin() as conn:
            conn.execute(
                recon_lookup_code.update()
                .where(
                    recon_lookup_code.c.LOOKUP_TYPE == "DB_COLUMN_MAPPING",
                    recon_lookup_code.c.LOOKUP_CODE == "CONT_NO",
                )
                .values(MEANING="Thùng Container To")
            )
        _clear_cache()

        # Khi mở lại template đã có: template vẫn giữ nguyên "Số container" (nhãn đã lưu)
        cols_after = list_columns(admin_ctx, version_id)
        cont_after = next(c for c in cols_after.data if c["field_name"] == "CONT_NO")
        assert cont_after["label"] == "Số container"
