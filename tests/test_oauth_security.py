import pytest
from cryptography.fernet import Fernet

from app.oauth_security import (
    OAuthSecurityError,
    create_oauth_state,
    decrypt_access_token,
    encrypt_access_token,
    validate_oauth_state,
)


def test_oauth_state_round_trip(monkeypatch):
    monkeypatch.setenv("OAUTH_STATE_SECRET", "x" * 48)
    state = create_oauth_state(now=1000)
    payload = validate_oauth_state(state, now=1100)
    assert payload["iat"] == 1000
    assert len(payload["nonce"]) >= 32


def test_oauth_state_rejects_tampering(monkeypatch):
    monkeypatch.setenv("OAUTH_STATE_SECRET", "x" * 48)
    state = create_oauth_state(now=1000)
    encoded, signature = state.split(".")
    tampered = encoded[:-1] + ("A" if encoded[-1] != "A" else "B") + "." + signature
    with pytest.raises(OAuthSecurityError):
        validate_oauth_state(tampered, now=1001)


def test_oauth_state_expires(monkeypatch):
    monkeypatch.setenv("OAUTH_STATE_SECRET", "x" * 48)
    state = create_oauth_state(now=1000)
    with pytest.raises(OAuthSecurityError, match="expired"):
        validate_oauth_state(state, now=1700, max_age_seconds=600)


def test_oauth_state_requires_secret(monkeypatch):
    monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)
    with pytest.raises(OAuthSecurityError, match="OAUTH_STATE_SECRET"):
        create_oauth_state(now=1000)


def test_token_encryption_round_trip(monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    token = "test-token-not-a-real-credential"
    encrypted = encrypt_access_token(token)
    assert encrypted != token
    assert decrypt_access_token(encrypted) == token


def test_token_encryption_rejects_missing_key(monkeypatch):
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    with pytest.raises(OAuthSecurityError, match="TOKEN_ENCRYPTION_KEY"):
        encrypt_access_token("sample")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: state + "%%%",
        lambda state: state + "é",
        lambda state: state.replace(".", "..", 1),
        lambda state: state + " ",
    ],
)
def test_oauth_state_rejects_noncanonical_encodings(monkeypatch, mutate):
    from app.oauth_security import create_oauth_state, validate_oauth_state, OAuthSecurityError

    monkeypatch.setenv("OAUTH_STATE_SECRET", "x" * 48)
    state = create_oauth_state(now=1000)
    with pytest.raises(OAuthSecurityError):
        validate_oauth_state(mutate(state), now=1000)


def test_oauth_state_rejects_boolean_issued_at(monkeypatch):
    import base64
    import hashlib
    import hmac
    import json

    from app.oauth_security import OAuthSecurityError, validate_oauth_state

    secret = "x" * 48
    monkeypatch.setenv("OAUTH_STATE_SECRET", secret)
    payload = {
        "iat": True,
        "nonce": "n" * 43,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).rstrip(b"=")
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), encoded, hashlib.sha256).digest()
    ).rstrip(b"=")
    signed_state = (encoded + b"." + signature).decode("ascii")

    with pytest.raises(OAuthSecurityError, match="payload"):
        validate_oauth_state(signed_state, now=1000)
