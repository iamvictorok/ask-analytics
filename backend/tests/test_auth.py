"""Auth tests — JWT round trip, expired token, tampered token."""
import time

from backend.config import Settings
from backend.app.auth.standalone_adapter import issue_token, verify_token
from backend.app.models import Identity


def _settings(**overrides):
    return Settings(jwt_secret="test-secret-key-32chars-minimum!", **overrides)


def test_jwt_roundtrip():
    settings = _settings()
    identity = Identity(
        user_id="analyst_01",
        role="external_stakeholder",
        permitted_org_units=["OU_KADUNA", "OU_KANO"],
        permitted_indicator_groups=["malaria"],
    )
    token = issue_token(identity, settings)
    assert isinstance(token, str)
    parts = token.split(".")
    assert len(parts) == 3

    result = verify_token(token, settings)
    assert result is not None
    assert result.user_id == "analyst_01"
    assert result.role == "external_stakeholder"
    assert "OU_KADUNA" in result.permitted_org_units


def test_expired_token_rejected():
    settings = Settings(jwt_secret="test-key", jwt_expire_seconds=0)
    identity = Identity(user_id="expired_user")
    token = issue_token(identity, settings)
    # Token was issued with exp = now + 0, so it should be expired
    time.sleep(1)
    result = verify_token(token, settings)
    assert result is None


def test_tampered_token_rejected():
    settings = _settings()
    identity = Identity(user_id="legit_user")
    token = issue_token(identity, settings)
    # Tamper with the payload
    parts = token.split(".")
    tampered = parts[0] + "." + parts[1] + "x" + "." + parts[2]
    result = verify_token(tampered, settings)
    assert result is None


def test_wrong_secret_rejected():
    settings_a = Settings(jwt_secret="secret-A")
    settings_b = Settings(jwt_secret="secret-B")
    identity = Identity(user_id="user_a")
    token = issue_token(identity, settings_a)
    result = verify_token(token, settings_b)
    assert result is None


def test_malformed_token_rejected():
    settings = _settings()
    assert verify_token("not.a.valid.jwt", settings) is None
    assert verify_token("", settings) is None
    assert verify_token("single_segment", settings) is None


def test_identity_defaults():
    settings = _settings()
    identity = Identity(user_id="minimal_user")
    token = issue_token(identity, settings)
    result = verify_token(token, settings)
    assert result is not None
    assert result.role == "external_stakeholder"
    assert result.permitted_org_units == []
    assert result.permitted_indicator_groups == []
