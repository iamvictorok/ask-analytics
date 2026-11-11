"""DHIS2 Route auth adapter.

When the backend sits behind a DHIS2 Route (``/api/routes/<code>/run/**``),
the DHIS2 server — not the browser — makes the HTTP call. The DHIS2 admin
configures the Route with an ``api-headers`` auth entry carrying a shared key
(``ROUTE_KEY_HEADER: ROUTE_SHARED_KEY``). DHIS2 stores that value encrypted and
adds it server-side, so it never reaches client code. DHIS2 also adds
``X-Forwarded-User`` with the username of the logged-in DHIS2 user.

A request is trusted only when the shared key matches (constant-time compare).
The forwarded username is then used for per-user history and rate limiting;
it is never trusted on its own.
"""
from __future__ import annotations

import hmac
import logging
import re
from typing import Mapping

from backend.config import Settings
from backend.app.models import Identity

logger = logging.getLogger("dhis2_analyst.route_auth")

# DHIS2 usernames: letters, digits and a few separators. Anything else is
# replaced so the value is safe as a history key / log field.
_USER_SAFE = re.compile(r"[^A-Za-z0-9._@\-]")


def _header(headers: Mapping[str, str], name: str) -> str:
    # Starlette headers are case-insensitive; plain dicts (tests) may not be.
    value = headers.get(name)
    if value is None:
        lower = name.lower()
        for k, v in headers.items():
            if k.lower() == lower:
                value = v
                break
    return (value or "").strip()


def route_key_valid(headers: Mapping[str, str], settings: Settings) -> bool:
    """True when the request carries the configured shared route key."""
    expected = (settings.route_shared_key or "").strip()
    if not settings.route_mode_enabled or not expected:
        return False
    supplied = _header(headers, settings.route_key_header)
    if not supplied:
        return False
    return hmac.compare_digest(supplied.encode(), expected.encode())


def route_identity(headers: Mapping[str, str], settings: Settings) -> Identity | None:
    """Return the Identity for a request proxied by a DHIS2 Route, else None."""
    if not route_key_valid(headers, settings):
        return None
    username = _USER_SAFE.sub("_", _header(headers, settings.route_user_header))[:128]
    if not username:
        # DHIS2 always sends X-Forwarded-User; a keyed call without it is a
        # misconfigured proxy, not a user. Refuse rather than share one history.
        logger.warning("route_request_without_user")
        return None
    return Identity(
        user_id=f"dhis2:{username}",
        role="dhis2_user",
        permitted_org_units=[],
        permitted_indicator_groups=[],
        auth_source="route",
    )
