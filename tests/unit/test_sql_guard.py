from __future__ import annotations

import pytest

from app.engine.sql_guard import check_sql

ALLOWED_PARAMS = ["p_from", "p_to", "p_org", "p_status"]


def test_sql_guard_valid_select() -> None:
    sql = "SELECT id, amount, invoice_date FROM invoices WHERE invoice_date >= :p_from AND invoice_date <= :p_to"
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is True
    assert err is None


def test_sql_guard_valid_with_cte() -> None:
    sql = """
    WITH filtered AS (
        SELECT id, amount, invoice_date FROM invoices
        WHERE invoice_date >= :p_from AND invoice_date <= :p_to AND org_code = :p_org
    )
    SELECT * FROM filtered
    """
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is True
    assert err is None


def test_sql_guard_valid_case_when_and_string_literals() -> None:
    sql = """
    SELECT
        id,
        CASE WHEN status = 'DROP' THEN 'CANCELLED' ELSE 'ACTIVE' END AS status_desc
    FROM orders
    WHERE order_date >= :p_from AND order_date <= :p_to
    """
    # Từ khóa 'DROP' nằm trong nháy đơn literal -> an toàn
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is True
    assert err is None


def test_sql_guard_valid_comments_ignored() -> None:
    sql = """
    -- This is a comment mentioning DROP TABLE or DELETE
    /* Another block comment with EXECUTE */
    SELECT id, invoice_date FROM invoices WHERE invoice_date >= :p_from AND invoice_date <= :p_to
    """
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is True
    assert err is None


def test_sql_guard_empty_sql() -> None:
    ok, err = check_sql("   ", ALLOWED_PARAMS)
    assert ok is False
    assert "trống" in (err or "").lower()


def test_sql_guard_semicolon_forbidden() -> None:
    sql = "SELECT * FROM inv WHERE d >= :p_from AND d <= :p_to;"
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is False
    assert "chấm phẩy" in (err or "").lower()


@pytest.mark.parametrize(
    "forbidden_sql, keyword",
    [
        ("INSERT INTO inv VALUES (1)", "INSERT"),
        ("UPDATE inv SET amount = 0", "UPDATE"),
        ("DELETE FROM inv", "DELETE"),
        ("MERGE INTO inv USING dual ON (1=1) WHEN MATCHED THEN UPDATE SET a=1", "MERGE"),
        ("DROP TABLE inv", "DROP"),
        ("CREATE TABLE test (id INT)", "CREATE"),
        ("ALTER TABLE inv ADD col INT", "ALTER"),
        ("TRUNCATE TABLE inv", "TRUNCATE"),
        ("GRANT SELECT ON inv TO user2", "GRANT"),
        ("REVOKE SELECT ON inv FROM user2", "REVOKE"),
        ("BEGIN dbms_output.put_line('hi'); END;", "BEGIN"),
        ("DECLARE x INT; BEGIN x := 1; END;", "DECLARE"),
        ("EXEC my_proc(:p_from)", "EXEC"),
        ("EXECUTE my_proc(:p_from)", "EXECUTE"),
        ("CALL my_proc(:p_from)", "CALL"),
        ("COMMIT", "COMMIT"),
        ("ROLLBACK", "ROLLBACK"),
        ("LOCK TABLE inv IN EXCLUSIVE MODE", "LOCK"),
    ],
)
def test_sql_guard_disallowed_start_commands(forbidden_sql: str, keyword: str) -> None:
    ok, err = check_sql(forbidden_sql, ALLOWED_PARAMS)
    assert ok is False
    assert err is not None


def test_sql_guard_for_update() -> None:
    sql = "SELECT * FROM inv WHERE d >= :p_from AND d <= :p_to FOR UPDATE"
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is False
    assert "FOR UPDATE" in (err or "").upper()


def test_sql_guard_dbms_package() -> None:
    sql = "SELECT DBMS_PIPE.RECEIVE_MESSAGE('a', 5) FROM dual WHERE d >= :p_from AND d <= :p_to"
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is False
    assert "DBMS_" in (err or "").upper()


def test_sql_guard_utl_package() -> None:
    sql = "SELECT UTL_HTTP.REQUEST('http://evil.com') FROM dual WHERE d >= :p_from AND d <= :p_to"
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is False
    assert "UTL_" in (err or "").upper()


def test_sql_guard_database_link() -> None:
    sql = "SELECT * FROM remote_table@db_link WHERE d >= :p_from AND d <= :p_to"
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is False
    assert "@" in (err or "")


def test_sql_guard_unknown_bind_param() -> None:
    sql = "SELECT * FROM inv WHERE d >= :p_from AND d <= :p_to AND org = :unknown_param"
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is False
    assert "unknown_param" in (err or "")


def test_sql_guard_missing_p_from() -> None:
    sql = "SELECT * FROM inv WHERE d <= :p_to"
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is False
    assert "p_from" in (err or "")


def test_sql_guard_missing_p_to() -> None:
    sql = "SELECT * FROM inv WHERE d >= :p_from"
    ok, err = check_sql(sql, ALLOWED_PARAMS)
    assert ok is False
    assert "p_to" in (err or "")
