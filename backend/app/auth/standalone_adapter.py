"""Standalone JWT auth adapter — HS256 tokens for external stakeholders.

Issues and verifies JWTs with HMAC-SHA256. Pure-Python — no PyJWT dependency.
Includes permission scoping (org units, indicator groups) in the payload.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

from backend.config import Settings
from backend.app.models import Identity

logger = logging.getLogger("dhis2_analyst.standalone_auth")


def issue_token(identity: Identity, settings: Settings) -> str:
    """Issue a signed JWT for the given identity."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = identity.model_dump()
    payload["iat"] = now
    payload["exp"] = now + settings.jwt_expire_seconds

    signing_input = f"{_b64(header)}.{_b64(payload)}"
    sig = hmac.new(
        settings.jwt_secret.encode(),
        signing_input.encode(),
        hashlib.sha256,
    ).digest()

    token = f"{signing_input}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"
    logger.info("jwt_issued", extra={"user_id": identity.user_id, "role": identity.role})
    return token


def verify_token(token: str, settings: Settings) -> Identity | None:
    """Verify a JWT and return the Identity, or None if invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        head, body, sig = parts
        expected = hmac.new(
            settings.jwt_secret.encode(),
            f"{head}.{body}".encode(),
            hashlib.sha256,
        ).digest()
        actual = base64.urlsafe_b64decode(_pad(sig))

        if not hmac.compare_digest(expected, actual):
            logger.debug("jwt_signature_mismatch")
            return None

        payload = json.loads(base64.urlsafe_b64decode(_pad(body)))

        # Check expiry
        exp = int(payload.get("exp", 0))
        if exp < int(time.time()):
            logger.debug("jwt_expired", extra={"exp": exp})
            return None

        # Build Identity from payload
        return Identity(
            user_id=payload.get("user_id", ""),
            role=payload.get("role", "external_stakeholder"),
            permitted_org_units=payload.get("permitted_org_units", []),
            permitted_indicator_groups=payload.get("permitted_indicator_groups", []),
            auth_source="standalone",
        )

    except Exception as exc:
        logger.debug("jwt_verify_error", extra={"error": str(exc)})
        return None


def _b64(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _pad(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode()
