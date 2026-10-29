"""Security primitives for the future server-side Instagram OAuth flow.

These helpers do not implement OAuth or provide replay protection by themselves.
OAuth state must also be stored and consumed once in durable shared storage.
"""
import base64
import hashlib
import hmac
import json
import os
import re
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
    """Validate canonical URL-safe encoding, signature, and age.

    Callers must additionally bind the state to the browser session and enforce
    one-time use in durable shared storage.
    """
    if not isinstance(state, str) or not state or len(state) > 2048 or state.count(".") != 1:
        raise OAuthSecurityError("Invalid OAuth state format.")
    try:
        raw_state = state.encode("ascii")
    except UnicodeEncodeError:
        raise OAuthSecurityError("Invalid OAuth state format.") from None

    encoded, supplied_signature = raw_state.split(b".", 1)
    if (
        not encoded
        or not supplied_signature
        or re.fullmatch(rb"[A-Za-z0-9_-]+", encoded) is None
        or re.fullmatch(rb"[A-Za-z0-9_-]+", supplied_signature) is None
    ):
        raise OAuthSecurityError("Invalid OAuth state format.")

    expected = hmac.new(_state_secret(), encoded, hashlib.sha256).digest()
    try:
        supplied = base64.urlsafe_b64decode(supplied_signature + b"=" * (-len(supplied_signature) % 4))
        payload_bytes = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
        # Reject alternate/non-canonical encodings instead of allowing the
        # permissive base64 decoder to silently ignore extra characters.
        if base64.urlsafe_b64encode(supplied).rstrip(b"=") != supplied_signature:
            raise OAuthSecurityError("Invalid OAuth state signature encoding.")
        if base64.urlsafe_b64encode(payload_bytes).rstrip(b"=") != encoded:
            raise OAuthSecurityError("Invalid OAuth state payload encoding.")
        payload = json.loads(payload_bytes)
    except OAuthSecurityError:
        raise
    except (ValueError, UnicodeDecodeError):
        raise OAuthSecurityError("Invalid OAuth state payload.") from None

    if not hmac.compare_digest(expected, supplied):
        raise OAuthSecurityError("Invalid OAuth state signature.")
    if not isinstance(payload, dict) or type(payload.get("iat")) is not int:
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
