"""Tests cho report SQL validator — Bước 1 task 22 (test viết trước).

check_report_sql: SELECT-only (SELECT/WITH), chặn DML/DDL/PLSQL,
multi-statement, FOR UPDATE, DB link, DBMS_/UTL_; phát hiện bind
variables (T22-01, T22-02, T22-03). Không bắt buộc :p_from/:p_to như
check_sql của template đối soát (Q2).
"""

from __future__ import annotations

import pytest

from app.engine.sql_guard import check_report_sql


def test_valid_select_with_binds() -> None:
    sql = "SELECT id, amount FROM fin_revenue WHERE org = :p_org AND d >= :p_from"
    ok, err, binds = check_report_sql(sql)
    assert ok is True
    assert err is None
    assert binds == ["p_from", "p_org"]


def test_valid_with_cte() -> None:
    sql = """
    WITH f AS (
        SELECT id, amount FROM fin_revenue WHERE org = :p_org
    )
    SELECT * FROM f
    """
    ok, err, binds = check_report_sql(sql)
    assert ok is True
    assert binds == ["p_org"]


def test_valid_select_no_binds() -> None:
    ok, err, binds = check_report_sql("SELECT id, amount FROM fin_revenue")
    assert ok is True
    assert binds == []


def test_duplicate_binds_deduped_and_sorted() -> None:
    sql = "SELECT * FROM t WHERE a = :p_b AND b = :p_a AND c = :p_b"
    ok, _, binds = check_report_sql(sql)
    assert ok is True
    assert binds == ["p_a", "p_b"]


def test_bind_inside_literal_not_discovered() -> None:
    sql = "SELECT ':p_org' AS label, amount FROM fin_revenue WHERE org = :p_org"
    ok, _, binds = check_report_sql(sql)
    assert ok is True
    assert binds == ["p_org"]


def test_empty_sql() -> None:
    ok, err, binds = check_report_sql("   ")
    assert ok is False
    assert "trống" in (err or "").lower()
    assert binds == []


def test_semicolon_forbidden() -> None:
    sql = "SELECT * FROM t WHERE a = :p_a; SELECT * FROM u"
    ok, err, _ = check_report_sql(sql)
    assert ok is False
    assert "chấm phẩy" in (err or "").lower()


@pytest.mark.parametrize(
    "forbidden_sql",
    [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 0",
        "DELETE FROM t",
        "MERGE INTO t USING dual ON (1=1) WHEN MATCHED THEN UPDATE SET a=1",
        "DROP TABLE t",
        "CREATE TABLE t (id INT)",
        "ALTER TABLE t ADD c INT",
        "TRUNCATE TABLE t",
        "GRANT SELECT ON t TO u2",
        "REVOKE SELECT ON t FROM u2",
        "BEGIN dbms_output.put_line('hi'); END;",
        "DECLARE x INT; BEGIN x := 1; END;",
        "EXEC my_proc(:p_a)",
        "EXECUTE my_proc(:p_a)",
        "CALL my_proc(:p_a)",
        "COMMIT",
        "ROLLBACK",
        "LOCK TABLE t IN EXCLUSIVE MODE",
    ],
)
def test_disallowed_statements(forbidden_sql: str) -> None:
    ok, err, _ = check_report_sql(forbidden_sql)
    assert ok is False
    assert err is not None


def test_for_update_forbidden() -> None:
    ok, err, _ = check_report_sql("SELECT * FROM t FOR UPDATE")
    assert ok is False
    assert "FOR UPDATE" in (err or "").upper()


def test_dbms_and_utl_forbidden() -> None:
    ok, err, _ = check_report_sql("SELECT DBMS_PIPE.RECEIVE_MESSAGE('a', 5) FROM dual")
    assert ok is False
    assert "DBMS_" in (err or "").upper()
    ok, err, _ = check_report_sql("SELECT UTL_HTTP.REQUEST('http://x') FROM dual")
    assert ok is False
    assert "UTL_" in (err or "").upper()


def test_database_link_forbidden() -> None:
    ok, err, _ = check_report_sql("SELECT * FROM remote_table@db_link")
    assert ok is False
    assert "@" in (err or "")


def test_keywords_in_literals_and_comments_ignored() -> None:
    sql = """
    -- DROP TABLE hay DELETE đều là chú thích
    /* EXECUTE trong block comment */
    SELECT id, CASE WHEN status = 'DROP' THEN 'X' ELSE 'Y' END FROM t
    """
    ok, err, binds = check_report_sql(sql)
    assert ok is True
    assert err is None
    assert binds == []


def test_no_p_from_p_to_required() -> None:
    """Khác check_sql: report SQL không bắt buộc :p_from/:p_to (Q2)."""
    ok, _, binds = check_report_sql("SELECT * FROM t WHERE org = :p_org")
    assert ok is True
    assert binds == ["p_org"]
