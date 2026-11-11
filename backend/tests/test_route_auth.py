"""DHIS2 Route mode: requests are trusted only with the shared route key."""
import asyncio
import secrets

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.config import Settings
from backend.app.auth.route_adapter import route_identity, route_key_valid
from backend.app.auth.standalone_adapter import issue_token
from backend.app.dhis2.client import DHIS2Client
from backend.app.models import Identity, LoginRequest
from backend.main import current_identity, login

# Generated per run: fixtures must never look like a real, reusable key.
KEY = secrets.token_hex(32)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _route_settings(**kw):
    base = dict(
        deployment_mode="route",
        route_shared_key=KEY,
        dhis2_base_url="https://dhis2.example.org",
        jwt_secret="x" * 32,
    )
    base.update(kw)
    return Settings(**base)


def _request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "method": "GET", "path": "/api/conversations", "headers": raw})


def test_valid_key_and_user_gives_route_identity():
    s = _route_settings()
    ident = route_identity({"X-Route-Key": KEY, "X-Forwarded-User": "admin"}, s)
    assert ident is not None
    assert ident.user_id == "dhis2:admin"
    assert ident.auth_source == "route"


def test_header_names_are_case_insensitive():
    s = _route_settings()
    assert route_key_valid({"x-route-key": KEY}, s)


def test_wrong_or_missing_key_rejected():
    s = _route_settings()
    assert route_identity({"X-Route-Key": "nope", "X-Forwarded-User": "admin"}, s) is None
    assert route_identity({"X-Forwarded-User": "admin"}, s) is None


def test_forwarded_user_alone_is_not_trusted():
    s = _route_settings()
    with pytest.raises(HTTPException) as exc:
        _run(current_identity(_request({"X-Forwarded-User": "admin"}), None, s))
    assert exc.value.status_code == 401


def test_key_without_user_rejected():
    s = _route_settings()
    assert route_identity({"X-Route-Key": KEY}, s) is None


def test_username_is_sanitised():
    s = _route_settings()
    ident = route_identity({"X-Route-Key": KEY, "X-Forwarded-User": "a b/../c"}, s)
    assert ident.user_id == "dhis2:a_b_.._c"


def test_custom_header_name():
    s = _route_settings(route_key_header="X-Backend-Key")
    assert route_key_valid({"X-Backend-Key": KEY}, s)
    assert not route_key_valid({"X-Route-Key": KEY}, s)


def test_route_mode_rejects_standalone_jwt():
    s = _route_settings()
    token = issue_token(Identity(user_id="someone"), s)
    with pytest.raises(HTTPException) as exc:
        _run(current_identity(_request({}), f"Bearer {token}", s))
    assert exc.value.status_code == 401


def test_route_mode_accepts_route_request():
    s = _route_settings()
    ident = _run(current_identity(_request({"X-Route-Key": KEY, "X-Forwarded-User": "jane"}), None, s))
    assert ident.user_id == "dhis2:jane"


def test_standalone_mode_ignores_route_headers():
    s = Settings(deployment_mode="standalone", route_shared_key=KEY, jwt_secret="x" * 32)
    assert not s.route_mode_enabled
    with pytest.raises(HTTPException):
        _run(current_identity(_request({"X-Route-Key": KEY, "X-Forwarded-User": "jane"}), None, s))


def test_combined_mode_accepts_route_and_jwt():
    s = Settings(deployment_mode="combined", route_shared_key=KEY, jwt_secret="x" * 32)
    assert s.route_mode_enabled
    ident = _run(current_identity(_request({"X-Route-Key": KEY, "X-Forwarded-User": "jane"}), None, s))
    assert ident.auth_source == "route"
    token = issue_token(Identity(user_id="standalone_user"), s)
    ident2 = _run(current_identity(_request({}), f"Bearer {token}", s))
    assert ident2.user_id == "standalone_user" and ident2.auth_source == "standalone"


def test_combined_mode_without_key_has_no_route_access():
    s = Settings(deployment_mode="combined", route_shared_key="", jwt_secret="x" * 32)
    assert not s.route_mode_enabled
    assert not route_key_valid({"X-Route-Key": ""}, s)


def test_login_disabled_in_route_mode():
    s = _route_settings()
    with pytest.raises(HTTPException) as exc:
        _run(login(LoginRequest(username="demo", password="x"), s))
    assert exc.value.status_code == 404


def test_route_mode_refuses_short_key():
    s = _route_settings(route_shared_key="short")
    with pytest.raises(SystemExit):
        s.startup_checks()


def test_route_mode_refuses_without_base_url():
    s = _route_settings(dhis2_base_url="")
    with pytest.raises(SystemExit):
        s.startup_checks()


def test_route_mode_starts_with_valid_config():
    s = _route_settings(llm_provider="mock", dhis2_pat="d2pat_test")
    s.startup_checks()  # must not exit


def test_server_side_pat_used_for_dhis2_calls():
    s = _route_settings(dhis2_pat="d2pat_server_side")
    kw = DHIS2Client(s)._build_client_kwargs()
    assert kw["headers"]["Authorization"] == "ApiToken d2pat_server_side"
    assert kw["auth"] is None
    assert s.has_dhis2_credentials


def test_per_user_pat_wins_over_server_pat():
    s = _route_settings(dhis2_pat="d2pat_server_side")
    kw = DHIS2Client(s, token="user_token")._build_client_kwargs()
    assert kw["headers"]["Authorization"] == "ApiToken user_token"
