"""Web enrichment node — real Tavily API integration.

Fires only when needs_web_enrichment=true AND TAVILY_API_KEY is set.
Falls back to SearxNG-compatible endpoint when TAVILY_ENDPOINT is overridden.
External stakeholders are blocked from web search by default.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from backend.config import Settings
from backend.app.agent.state import AgentState

logger = logging.getLogger("dhis2_analyst.web_enrichment")

TAVILY_DEFAULT_ENDPOINT = "https://api.tavily.com/search"


async def enrich_web(state: AgentState, settings: Settings) -> AgentState:
    import time
    start_time = time.time()

    logger.info(
        "web_enrichment_start",
        extra={
            "needs_web_enrichment": state.get("needs_web_enrichment"),
            "queries": state.get("web_search_queries", []),
            "user_role": state.get("user_role"),
        }
    )

    if not state["needs_web_enrichment"]:
        state["web_context"] = []
        logger.info("web_enrichment_skipped", extra={"reason": "not_needed"})
        return state

    # External stakeholders cannot trigger web search by default
    if state["user_role"] == "external_stakeholder":
        logger.debug("web_search_blocked_for_external_stakeholder")
        state["web_context"] = []
        return state

    queries = state["web_search_queries"][:3]
    if not queries:
        state["web_context"] = []
        logger.info("web_enrichment_skipped", extra={"reason": "no_queries"})
        return state

    if settings.audit_web_search:
        logger.info(
            "web_search_requested",
            extra={
                "session_id": state["session_id"],
                "user_id": state["user_id"],
                "query_count": len(queries),
                "queries": queries,
            },
        )

    if not settings.tavily_api_key:
        state["web_context"] = [{
            "title": "Web enrichment unavailable",
            "url": "local://web-enrichment-disabled",
            "content": "No Tavily API key is configured. Set TAVILY_API_KEY in .env to enable web enrichment.",
            "score": 1.0,
        }]
        logger.warning("web_enrichment_unavailable_no_key")
        return state

    endpoint = settings.tavily_endpoint or TAVILY_DEFAULT_ENDPOINT
    trusted = settings.trusted_domains

    all_results: list[dict] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for query in queries:
            try:
                payload = {
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_domains": trusted if trusted else None,
                }
                # Remove None values
                payload = {k: v for k, v in payload.items() if v is not None}

                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                added_count = 0
                for result in results:
                    score = float(result.get("score", result.get("relevance_score", 0.0)))

                    # Filter by relevance score
                    if score < 0.7:
                        continue

                    # Filter by trusted domains
                    url = result.get("url", "")
                    if trusted and not _domain_trusted(url, trusted):
                        continue

                    all_results.append({
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("content", "")[:2000],
                        "score": score,
                    })
                    added_count += 1

                if settings.audit_web_search:
                    logger.info(
                        "web_search_complete",
                        extra={
                            "session_id": state["session_id"],
                            "query": query,
                            "raw_results": len(results),
                            "filtered_results": added_count,
                        },
                    )

            except httpx.HTTPStatusError as exc:
                logger.error(
                    "tavily_http_error",
                    extra={"query": query, "status": exc.response.status_code},
                )
            except Exception as exc:
                logger.error(
                    "tavily_error",
                    extra={"query": query, "error": str(exc)},
                )

    # Deduplicate by URL and limit to 15 results
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for r in sorted(all_results, key=lambda x: -x["score"]):
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique.append(r)
        if len(unique) >= 15:
            break

    state["web_context"] = unique
    duration = time.time() - start_time
    logger.info(
        "web_enrichment_complete",
        extra={
            "results_count": len(unique),
            "duration_seconds": round(duration, 4),
        }
    )
    return state


def _domain_trusted(url: str, trusted_domains: list[str]) -> bool:
    """Check if a URL domain matches the trusted domain list."""
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()
    except Exception:
        return False

    for domain in trusted_domains:
        domain = domain.lstrip(".")
        if hostname == domain or hostname.endswith(f".{domain}"):
            return True
    return False
