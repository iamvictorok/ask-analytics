from __future__ import annotations

import logging
from backend.app.agent.state import AgentState

logger = logging.getLogger("dhis2_analyst.renderer.export")


def render_export_payload(state: AgentState) -> dict:
    """Return the normalised data payload for export endpoints."""
    data = state.get("dhis2_data", {})
    rows = data.get("rows", [])
    logger.info("render_export_start", extra={"rows_count": len(rows)})

    sources = []
    for ctx in state.get("web_context", []):
        if not ctx.get("url", "").startswith("local://"):
            sources.append({
                "title": ctx.get("title", ""),
                "url": ctx.get("url", ""),
                "confidence": ctx.get("score", 0.0),
            })
    payload = {
        "rows": rows,
        "headers": data.get("headers", []),
        "metadata": data.get("metadata", {}),
        "sources": sources,
    }
    logger.info("render_export_complete", extra={"payload_keys": list(payload.keys())})
    return payload
