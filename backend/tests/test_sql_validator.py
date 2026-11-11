"""SQL validator tests — including injection patterns."""
from backend.app.agent.nodes.fetch_sql import validate_readonly_sql


def test_allows_safe_select():
    ok, reason = validate_readonly_sql("SELECT * FROM analytics LIMIT 10")
    assert ok, reason


def test_allows_analytics_materialized_views():
    ok, reason = validate_readonly_sql("SELECT * FROM analytics_2024 WHERE value > 0")
    assert ok, reason


def test_allows_join():
    ok, reason = validate_readonly_sql(
        "SELECT ou.name, dv.value FROM datavalue dv JOIN organisationunit ou ON ou.uid = dv.sourceid"
    )
    assert ok, reason


def test_rejects_mutation_delete():
    ok, _ = validate_readonly_sql("DELETE FROM datavalue")
    assert not ok


def test_rejects_mutation_insert():
    ok, _ = validate_readonly_sql("INSERT INTO datavalue VALUES (1, 2, 3)")
    assert not ok


def test_rejects_mutation_update():
    ok, _ = validate_readonly_sql("UPDATE dataelement SET name = 'x'")
    assert not ok


def test_rejects_drop():
    ok, _ = validate_readonly_sql("DROP TABLE datavalue")
    assert not ok


def test_rejects_truncate():
    ok, _ = validate_readonly_sql("TRUNCATE TABLE analytics")
    assert not ok


def test_rejects_unknown_table():
    ok, reason = validate_readonly_sql("SELECT * FROM users")
    assert not ok
    assert "allowlisted" in reason.lower() or "users" in reason


def test_rejects_information_schema():
    ok, _ = validate_readonly_sql("SELECT * FROM information_schema.tables")
    assert not ok


def test_rejects_pg_tables():
    ok, _ = validate_readonly_sql("SELECT * FROM pg_tables")
    assert not ok


def test_rejects_union_injection():
    ok, reason = validate_readonly_sql("SELECT * FROM analytics UNION SELECT * FROM pg_tables")
    assert not ok


def test_rejects_comment_injection():
    ok, reason = validate_readonly_sql("SELECT * FROM analytics -- DROP TABLE analytics")
    assert not ok


def test_rejects_semicolon_injection():
    ok, reason = validate_readonly_sql("SELECT 1 FROM analytics; SELECT * FROM pg_tables")
    assert not ok


def test_rejects_subquery_forbidden_table():
    ok, reason = validate_readonly_sql(
        "SELECT * FROM analytics WHERE value IN (SELECT id FROM users)"
    )
    assert not ok


def test_rejects_grant():
    ok, _ = validate_readonly_sql("GRANT ALL ON analytics TO public")
    assert not ok


def test_rejects_set_role():
    ok, _ = validate_readonly_sql("SET ROLE postgres; SELECT * FROM analytics")
    assert not ok


def test_rejects_empty():
    ok, _ = validate_readonly_sql("")
    assert not ok


def test_rejects_non_select():
    ok, reason = validate_readonly_sql("CREATE TABLE evil (id int)")
    assert not ok
    assert "SELECT" in reason or "forbidden" in reason.lower()
