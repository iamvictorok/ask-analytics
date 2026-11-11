"""DHIS2 auth adapter — validates DHIS2 API tokens via /api/me.

Used when DEPLOYMENT_MODE=dhis2 or combined. Extracts user identity,
org unit assignments, and roles from the DHIS2 user profile.
"""
from __future__ import annotations

import logging

import httpx

from backend.config import Settings
from backend.app.models import Identity

logger = logging.getLogger("dhis2_analyst.dhis2_auth")


async def extract_dhis2_token(authorization: str | None = None) -> str | None:
    """Extract token from Authorization header."""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() in {"apitoken", "bearer"} and value:
        return value
    return None


async def validate_dhis2_token(token: str, settings: Settings) -> Identity | None:
    """Validate a DHIS2 token by calling /api/me on the DHIS2 instance.

    Returns an Identity if valid, None if the token is rejected.
    """
    base_url = settings.dhis2_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{base_url}/api/me.json",
                params={"fields": "id,name,organisationUnits[id],userRoles[name]"},
                headers={"Authorization": f"ApiToken {token}"},
            )
            if response.status_code != 200:
                logger.debug(
                    "dhis2_token_rejected",
                    extra={"status": response.status_code},
                )
                return None

            profile = response.json()
            user_id = profile.get("id", "")
            org_units = [
                ou.get("id", "")
                for ou in profile.get("organisationUnits", [])
                if ou.get("id")
            ]
            roles = [
                r.get("name", "")
                for r in profile.get("userRoles", [])
            ]

            logger.info(
                "dhis2_token_valid",
                extra={
                    "user_id": user_id,
                    "org_units": len(org_units),
                    "roles": roles[:5],
                },
            )

            return Identity(
                user_id=user_id,
                role="dhis2_user",
                permitted_org_units=org_units,
                permitted_indicator_groups=[],
                auth_source="dhis2_pat",
            )

    except Exception as exc:
        logger.error(
            "dhis2_token_validation_error",
            extra={"error": str(exc)},
        )
        return None
