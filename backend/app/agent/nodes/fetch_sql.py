"""SQL fetch node — gated behind ENABLE_DIRECT_SQL=true.

Validates all SQL against an allowlist before execution. Enforces:
- SELECT-only
- Allowlisted tables only
- No forbidden keywords (DROP, INSERT, etc.)
- Row limit (max_rows from settings)
- Query timeout (sql_timeout_seconds from settings)
- Audit log per query
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("dhis2_analyst.fetch_sql")

ALLOWED_TABLES = frozenset({
    "datavalue",
    "analytics",
    "organisationunit",
    "dataelement",
    "indicator",
    "period",
    "categoryoptioncombo",
})

FORBIDDEN = re.compile(
    r"\b(drop|insert|update|delete|truncate|create|alter|pg_|information_schema"
    r"|grant|revoke|copy|execute|do\s+\$|set\s+role|set\s+session)\b",
    re.I,
)

# Detect common injection patterns
INJECTION_PATTERNS = re.compile(
    r"(--|/\*|\*/|;\s*select|union\s+select|union\s+all\s+select"
    r"|into\s+outfile|into\s+dumpfile|load_file|benchmark\s*\()",
    re.I,
)

SAFE_LITERAL = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _safe_sql_literal(value: Any, field: str) -> str:
    """Return a quoted SQL literal after strict allowlist validation."""
    text_value = str(value)
    if not SAFE_LITERAL.fullmatch(text_value):
        raise ValueError(f"Unsafe {field} value for SQL builder.")
    return f"'{text_value}'"


def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    """Validate that SQL is a safe read-only SELECT. Returns (ok, reason)."""
    stripped = sql.strip().rstrip(";")

    if not stripped:
        return False, "Empty SQL statement."

    if not stripped.lower().startswith("select "):
        return False, "Only SELECT statements are allowed."

    if FORBIDDEN.search(stripped):
        return False, "Statement contains a forbidden keyword or schema reference."

    if INJECTION_PATTERNS.search(stripped):
        return False, "Statement contains a suspicious injection pattern."

    # Check referenced tables against allowlist
    table_refs = re.findall(
        r"\b(?:from|join)\s+([a-zA-Z_][\w]*)", stripped, flags=re.I
    )
    unknown = [
        t for t in table_refs
        if t.lower() not in ALLOWED_TABLES and not t.lower().startswith("analytics_")
    ]
    if unknown:
        return False, f"Table not allowlisted: {', '.join(sorted(set(unknown)))}"

    # Check for subqueries referencing forbidden tables
    subquery_tables = re.findall(r"\(\s*select\s+.*?\bfrom\s+(\w+)", stripped, flags=re.I)
    unknown_sub = [
        t for t in subquery_tables
        if t.lower() not in ALLOWED_TABLES and not t.lower().startswith("analytics_")
    ]
    if unknown_sub:
        return False, f"Subquery references forbidden table: {', '.join(sorted(set(unknown_sub)))}"

    return True, "ok"


def build_analytics_sql(state: dict[str, Any]) -> str:
    """Build a simple analytics query from agent state. This is a basic SQL
    builder — the LLM may generate more sophisticated queries in production."""
    metrics = state.get("metrics", [])
    org = state.get("org_unit", {})
    periods = state.get("periods", [])

    if not metrics:
        raise ValueError("Cannot build analytics SQL without at least one metric.")
    if not periods:
        raise ValueError("Cannot build analytics SQL without at least one period.")

    metric_uids = ", ".join(_safe_sql_literal(m["uid"], "metric uid") for m in metrics)
    period_list = ", ".join(_safe_sql_literal(p, "period") for p in periods)
    org_uid = org.get("uid", "NATIONAL")
    org_literal = _safe_sql_literal(org_uid, "org unit uid")

    return f"""
        SELECT ou.name, p.iso, dv.value, de.name
        FROM datavalue dv
        JOIN dataelement de ON de.uid = dv.dataelementid
        JOIN organisationunit ou ON ou.uid = dv.sourceid
        JOIN period p ON p.periodid = dv.periodid
        WHERE de.uid IN ({metric_uids})
          AND ou.uid = {org_literal}
          AND p.iso IN ({period_list})
        ORDER BY p.iso
    """.strip()


async def execute_validated_sql(
    sql: str,
    session,
    timeout_seconds: int = 10,
) -> tuple[list[list[Any]], list[str]]:
    """Execute validated read-only SQL with timeout and row limit.

    Returns (rows, headers) tuple.
    """
    import asyncio
    from sqlalchemy import text

    ok, reason = validate_readonly_sql(sql)
    if not ok:
        logger.warning("sql_rejected", extra={"reason": reason, "sql_preview": sql[:200]})
        raise ValueError(f"SQL validation failed: {reason}")

    # Enforce row limit
    limited_sql = sql.rstrip().rstrip(";")
    if "limit" not in limited_sql.lower():
        limited_sql += " LIMIT 10000"

    logger.info("sql_execute", extra={"sql_preview": limited_sql[:200], "timeout": timeout_seconds})

    try:
        result = await asyncio.wait_for(
            session.execute(text(limited_sql)),
            timeout=timeout_seconds,
        )
        rows_raw = result.fetchall()
        headers = list(result.keys()) if hasattr(result, "keys") else []
        rows = [list(r) for r in rows_raw]

        logger.info("sql_result", extra={"row_count": len(rows)})
        return rows, headers

    except asyncio.TimeoutError:
        logger.error("sql_timeout", extra={"timeout": timeout_seconds})
        raise TimeoutError(f"SQL query exceeded {timeout_seconds}s timeout")
