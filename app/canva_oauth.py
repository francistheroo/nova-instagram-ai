"""Canva Connect OAuth 2.0 Authorization Code flow with PKCE (S256)."""
import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.oauth_security import OAuthSecurityError, create_oauth_state, validate_oauth_state
from app.oauth_utils import token_expiry_from_seconds
from app.oauth_store import OAuthStoreError, consume_oauth_state, save_oauth_state
from app.security import require_user
from app.canva_store import (
    CanvaStoreError,
    CanvaRefreshInProgress,
    canva_refresh_lock,
    load_latest_canva_tokens,
    mark_canva_refresh_pending,
    clear_canva_refresh_pending,
    save_canva_tokens,
)

router = APIRouter(prefix="/oauth/canva", tags=["Canva OAuth"], dependencies=[Depends(require_user)])


def _config() -> tuple[str, str, str]:
    client_id = os.getenv("CANVA_CLIENT_ID", "").strip()
    redirect_uri = os.getenv("CANVA_REDIRECT_URI", "").strip()
    client_secret = os.getenv("CANVA_CLIENT_SECRET", "").strip()
    if not client_id or not redirect_uri or not client_secret:
        raise HTTPException(status_code=503, detail="Configure CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, and CANVA_REDIRECT_URI on the server.")
    if not redirect_uri.startswith("https://"):
        raise HTTPException(status_code=503, detail="CANVA_REDIRECT_URI must use HTTPS.")
    return client_id, client_secret, redirect_uri


def _require_nova_key(x_nova_api_key: str | None = Header(default=None)):
    expected = os.getenv("NOVA_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Set NOVA_API_KEY in server environment before using Canva refresh.")
    if not x_nova_api_key or not secrets.compare_digest(x_nova_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-NOVA-API-Key.")
    return True


@router.get("/start")
async def canva_oauth_start():
    client_id, _, redirect_uri = _config()
    try:
        state = create_oauth_state()
        payload = validate_oauth_state(state)
        save_oauth_state(payload["nonce"], expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    except (OAuthSecurityError, OAuthStoreError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Canva OAuth security storage is not ready. Check server configuration.") from None

    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    scopes = os.getenv("CANVA_OAUTH_SCOPES", "design:content:read design:content:write design:meta:read")
    query = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    response = RedirectResponse(f"https://www.canva.com/api/oauth/authorize?{query}", status_code=302)
    response.set_cookie("nova_canva_oauth_state", state, httponly=True, secure=True, samesite="lax", max_age=600, path="/oauth/canva")
    response.set_cookie("nova_canva_pkce_verifier", verifier, httponly=True, secure=True, samesite="lax", max_age=600, path="/oauth/canva")
    return response


@router.get("/callback")
async def canva_oauth_callback(
    request: Request,
    code: str | None = Query(default=None, max_length=4096),
    state: str | None = Query(default=None, max_length=2048),
    error: str | None = Query(default=None, max_length=200),
):
    if error:
        raise HTTPException(status_code=400, detail="Canva authorization was not completed.")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Canva OAuth callback is missing code or state.")
    if not secrets.compare_digest(state, request.cookies.get("nova_canva_oauth_state", "")):
        raise HTTPException(status_code=400, detail="Canva OAuth state did not match this browser session.")
    verifier = request.cookies.get("nova_canva_pkce_verifier", "")
    if not verifier:
        raise HTTPException(status_code=400, detail="Canva OAuth PKCE verifier is missing. Restart the connection flow.")

    client_id, client_secret, redirect_uri = _config()
    try:
        payload = validate_oauth_state(state)
        if not consume_oauth_state(payload["nonce"]):
            raise HTTPException(status_code=400, detail="Canva OAuth state was already used or expired.")
    except OAuthSecurityError:
        raise HTTPException(status_code=400, detail="Canva OAuth state is invalid or expired.") from None
    except (OAuthStoreError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Canva OAuth state storage is unavailable.") from None

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.canva.com/rest/v1/oauth/token",
                auth=(client_id, client_secret),
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.is_error:
            raise HTTPException(status_code=502, detail="Canva token exchange failed. Check the Canva app redirect URI and PKCE configuration.")
        token_payload = response.json()
        if not isinstance(token_payload, dict):
            raise HTTPException(status_code=502, detail="Canva did not return a valid token response.")
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise HTTPException(status_code=502, detail="Canva did not return an access token.")
        expires_at = token_expiry_from_seconds(token_payload.get("expires_in"))
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(status_code=502, detail="Canva token exchange could not be completed. Check the provider configuration without logging credentials.") from None

    try:
        save_canva_tokens(token_payload, expires_at=expires_at)
    except (CanvaStoreError, OAuthStoreError, OAuthSecurityError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Canva issued tokens but NOVA could not store them securely. Restore database and encryption-key configuration, then restart the Canva connection flow; do not retry this authorization code.",
        ) from None

    response = RedirectResponse("/?canva_connected=pending_verification", status_code=303)
    response.delete_cookie("nova_canva_oauth_state", path="/oauth/canva")
    response.delete_cookie("nova_canva_pkce_verifier", path="/oauth/canva")
    return response


@router.post("/refresh")
async def canva_oauth_refresh(_: bool = Depends(_require_nova_key)):
    """Refresh Canva tokens under a cross-worker PostgreSQL lock."""
    client_id, client_secret, _ = _config()
    try:
        with canva_refresh_lock():
            return await _refresh_canva_tokens_locked(client_id, client_secret)
    except CanvaRefreshInProgress:
        raise HTTPException(
            status_code=409,
            detail="A Canva token refresh is already in progress. Retry after it finishes.",
        ) from None
    except (CanvaStoreError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Canva refresh storage is unavailable. Try again after database connectivity is restored.",
        ) from None


async def _refresh_canva_tokens_locked(client_id: str, client_secret: str):
    """Perform token rotation while the shared database lock is held."""
    try:
        current = load_latest_canva_tokens()
    except (CanvaStoreError, OAuthSecurityError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Canva token storage is unavailable or could not be decrypted.") from None
    if not current:
        raise HTTPException(status_code=503, detail="Canva is not connected. Complete /oauth/canva/start first.")
    if not isinstance(current, dict):
        raise HTTPException(status_code=503, detail="Stored Canva credentials are malformed. Reconnect Canva.")

    refresh_token = current.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        raise HTTPException(status_code=503, detail="No Canva refresh token is stored. Reconnect Canva to grant access again.")
    user_id = current.get("user_id")
    account_key = str(user_id).strip() if user_id is not None else os.getenv("CANVA_ACCOUNT_KEY", "").strip() or "default"

    # Persist this marker before sending the single-use refresh token to Canva.
    # If the request times out or saving the rotated bundle fails, all subsequent
    # token reads fail closed until a fresh OAuth connection replaces the bundle.
    try:
        mark_canva_refresh_pending(account_key)
    except (CanvaStoreError, OAuthSecurityError, OAuthStoreError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Canva refresh state could not be recorded safely. No provider request was made.",
        ) from None

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.canva.com/rest/v1/oauth/token",
                auth=(client_id, client_secret),
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.is_error:
            if response.status_code in (400, 401, 403):
                raise HTTPException(
                    status_code=409,
                    detail="Canva rejected the stored refresh token. Reconnect Canva and authorize access again.",
                )
            if response.status_code == 429:
                try:
                    clear_canva_refresh_pending(account_key)
                except (CanvaStoreError, OAuthSecurityError, OAuthStoreError, psycopg.Error):
                    raise HTTPException(
                        status_code=503,
                        detail="Canva rate-limited token refresh and NOVA could not clear its safety marker. Reconnect Canva before retrying.",
                    ) from None
                raise HTTPException(
                    status_code=503,
                    detail="Canva temporarily rate-limited token refresh. No token rotation occurred; retry later.",
                )
            raise HTTPException(
                status_code=502,
                detail="Canva token refresh failed due to a provider error. Verify the connection before retrying because refresh tokens are single-use.",
            )

        replacement = response.json()
        if (
            not isinstance(replacement, dict)
            or not isinstance(replacement.get("access_token"), str)
            or not replacement["access_token"].strip()
            or not isinstance(replacement.get("refresh_token"), str)
            or not replacement["refresh_token"].strip()
        ):
            raise HTTPException(
                status_code=502,
                detail="Canva did not return a complete replacement token bundle. Reconnect Canva if the current refresh token no longer works.",
            )

        if user_id and not replacement.get("user_id"):
            replacement["user_id"] = user_id
        expires_at = token_expiry_from_seconds(replacement.get("expires_in"))
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError, OverflowError):
        raise HTTPException(
            status_code=502,
            detail="Canva token refresh could not be completed. Verify the account before retrying because refresh tokens are single-use.",
        ) from None

    try:
        save_canva_tokens(replacement, expires_at=expires_at)
    except (CanvaStoreError, OAuthSecurityError, OAuthStoreError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Canva issued a replacement token bundle but NOVA could not save it securely. Fix database and encryption-key configuration, then reconnect Canva if needed; do not retry with the old refresh token.",
        ) from None

    return {
        "refreshed": True,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "token_returned": False,
    }
