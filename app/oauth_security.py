"""Security primitives for the future server-side Instagram OAuth flow.

These helpers do not implement OAuth or provide replay protection by themselves.
OAuth state must also be stored and consumed once in durable shared storage.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class OAuthSecurityError(ValueError):
    """Raised when OAuth state or an encrypted token is invalid."""


def _state_secret() -> bytes:
    secret = os.getenv("OAUTH_STATE_SECRET", "")
    if len(secret) < 32:
        raise OAuthSecurityError("OAUTH_STATE_SECRET must be at least 32 characters.")
    return secret.encode("utf-8")


def create_oauth_state(*, now: int | None = None) -> str:
    """Create a signed, timestamped, unpredictable state value."""
    timestamp = int(time.time() if now is None else now)
    payload = {
        "iat": timestamp,
        "nonce": secrets.token_urlsafe(32),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).rstrip(b"=")
    signature = hmac.new(_state_secret(), encoded, hashlib.sha256).digest()
    signature_encoded = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return (encoded + b"." + signature_encoded).decode("ascii")


def validate_oauth_state(state: str, *, max_age_seconds: int = 600, now: int | None = None) -> dict[str, Any]:
    """Validate signature and age. Caller must additionally enforce one-time use."""
    if not state or len(state) > 2048 or state.count(".") != 1:
        raise OAuthSecurityError("Invalid OAuth state format.")
    encoded, supplied_signature = state.encode("ascii", errors="ignore").split(b".", 1)
    expected = hmac.new(_state_secret(), encoded, hashlib.sha256).digest()
    try:
        supplied = base64.urlsafe_b64decode(supplied_signature + b"=" * (-len(supplied_signature) % 4))
        payload_bytes = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
        payload = json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError):
        raise OAuthSecurityError("Invalid OAuth state payload.") from None
    if not hmac.compare_digest(expected, supplied):
        raise OAuthSecurityError("Invalid OAuth state signature.")
    if not isinstance(payload, dict) or not isinstance(payload.get("iat"), int):
        raise OAuthSecurityError("Invalid OAuth state payload.")
    current = int(time.time() if now is None else now)
    age = current - payload["iat"]
    if age < 0 or age > max_age_seconds:
        raise OAuthSecurityError("OAuth state has expired.")
    if not isinstance(payload.get("nonce"), str) or len(payload["nonce"]) < 32:
        raise OAuthSecurityError("Invalid OAuth state nonce.")
    return payload


def encrypt_access_token(token: str) -> str:
    """Encrypt a token using a Fernet key stored only in the server environment."""
    key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise OAuthSecurityError("TOKEN_ENCRYPTION_KEY is not configured.")
    if not token:
        raise OAuthSecurityError("Cannot encrypt an empty token.")
    try:
        return Fernet(key.encode("ascii")).encrypt(token.encode("utf-8")).decode("ascii")
    except (ValueError, TypeError):
        raise OAuthSecurityError("TOKEN_ENCRYPTION_KEY must be a valid Fernet key.") from None


def decrypt_access_token(ciphertext: str) -> str:
    """Decrypt a stored token; never log the plaintext token."""
    key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise OAuthSecurityError("TOKEN_ENCRYPTION_KEY is not configured.")
    try:
        return Fernet(key.encode("ascii")).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError, UnicodeError):
        raise OAuthSecurityError("Token ciphertext or encryption key is invalid.") from None
