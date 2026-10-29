"""Server-side Instagram Login OAuth routes.

Configure the Instagram Login product in Meta and register the exact HTTPS
callback URL before enabling these routes in production.
"""
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import psycopg
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.oauth_security import OAuthSecurityError, create_oauth_state, validate_oauth_state
from app.oauth_utils import token_expiry_from_seconds
from app.oauth_store import (
    OAuthStoreError,
    InstagramRefreshInProgress,
    instagram_refresh_lock,
    consume_oauth_state,
    save_instagram_token,
    save_oauth_state,
    load_latest_instagram_token,
)

router = APIRouter(prefix="/oauth/instagram", tags=["Instagram OAuth"])
STATE_COOKIE = "nova_instagram_oauth_state"
STATE_MAX_AGE_SECONDS = 600
DEFAULT_SCOPES = "instagram_business_basic,instagram_business_manage_messages"


def _config() -> dict[str, str]:
    config = {
        "client_id": os.getenv("INSTAGRAM_OAUTH_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("INSTAGRAM_OAUTH_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.getenv("INSTAGRAM_OAUTH_REDIRECT_URI", "").strip(),
        "scopes": os.getenv("INSTAGRAM_OAUTH_SCOPES", DEFAULT_SCOPES).strip(),
        "api_version": os.getenv("META_API_VERSION", "v25.0").strip("/"),
    }
    if not all(config[key] for key in ("client_id", "client_secret", "redirect_uri", "scopes", "api_version")):
        raise HTTPException(
            status_code=503,
            detail="Instagram OAuth is not configured. Set the Instagram OAuth client ID, client secret, redirect URI, scopes, and API version in server environment settings.",
        )
    if not config["redirect_uri"].startswith("https://"):
        raise HTTPException(status_code=503, detail="Instagram OAuth redirect URI must use HTTPS.")
    return config


@router.get("/start")
async def instagram_oauth_start():
    """Create and persist OAuth state, then redirect the browser to Instagram."""
    config = _config()
    try:
        state = create_oauth_state()
        payload = validate_oauth_state(state)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=STATE_MAX_AGE_SECONDS)
        save_oauth_state(payload["nonce"], expires_at=expires_at)
    except (OAuthSecurityError, OAuthStoreError):
        raise HTTPException(
            status_code=503,
            detail="OAuth security or database storage is not configured correctly.",
        ) from None

    query = urlencode({
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": config["scopes"],
        "state": state,
    })
    response = RedirectResponse(
        url=f"https://www.instagram.com/oauth/authorize?{query}",
        status_code=302,
    )
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        max_age=STATE_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/oauth/instagram",
    )
    return response


@router.get("/callback")
async def instagram_oauth_callback(
    request: Request,
    code: str | None = Query(default=None, max_length=4096),
    state: str | None = Query(default=None, max_length=2048),
    error: str | None = Query(default=None, max_length=200),
):
    """Validate the browser-bound state, exchange the code, and store the long-lived token."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key=STATE_COOKIE, path="/oauth/instagram", secure=True, httponly=True, samesite="lax")

    if error:
        raise HTTPException(status_code=400, detail="Instagram authorization was cancelled or denied.")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Instagram callback is missing required parameters.")
    cookie_state = request.cookies.get(STATE_COOKIE)
    if not cookie_state or not __import__("hmac").compare_digest(cookie_state, state):
        raise HTTPException(status_code=400, detail="Instagram OAuth state did not match this browser session.")

    config = _config()
    try:
        payload = validate_oauth_state(state, max_age_seconds=STATE_MAX_AGE_SECONDS)
        if not consume_oauth_state(payload["nonce"]):
            raise OAuthSecurityError("OAuth state was already used or expired.")
    except (OAuthSecurityError, OAuthStoreError):
        raise HTTPException(status_code=400, detail="Instagram OAuth state is invalid, expired, or already used.") from None

    # OAuth code exchange is performed only on the server; never return tokens to the browser.
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            short_response = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "grant_type": "authorization_code",
                    "redirect_uri": config["redirect_uri"],
                    "code": code,
                },
            )
            if short_response.is_error:
                raise HTTPException(status_code=502, detail="Instagram authorization-code exchange failed.")
            short_payload = short_response.json()
            if not isinstance(short_payload, dict):
                raise HTTPException(status_code=502, detail="Instagram did not return a valid authorization response.")
            short_token = short_payload.get("access_token")
            raw_user_id = short_payload.get("user_id")
            if (
                not isinstance(short_token, str)
                or not short_token.strip()
                or isinstance(raw_user_id, bool)
                or not isinstance(raw_user_id, (str, int))
                or not str(raw_user_id).strip()
            ):
                raise HTTPException(status_code=502, detail="Instagram did not return the expected authorization response.")
            user_id = str(raw_user_id).strip()

            long_response = await client.get(
                f"https://graph.instagram.com/{config['api_version']}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": config["client_secret"],
                    "access_token": short_token,
                },
            )
            if long_response.is_error:
                raise HTTPException(status_code=502, detail="Instagram long-lived token exchange failed.")
            long_payload = long_response.json()
            if not isinstance(long_payload, dict):
                raise HTTPException(status_code=502, detail="Instagram did not return a valid long-lived token response.")
            long_token = long_payload.get("access_token")
            if not isinstance(long_token, str) or not long_token.strip():
                raise HTTPException(status_code=502, detail="Instagram did not return a long-lived access token.")
            expires_at = token_expiry_from_seconds(long_payload.get("expires_in"))
            save_instagram_token(user_id, long_token, expires_at=expires_at)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError, OAuthStoreError, OAuthSecurityError):
        raise HTTPException(
            status_code=502,
            detail="Instagram connection could not be completed. Check server configuration and logs without logging secrets.",
        ) from None

    # The redirect contains no access token or account credential.
    response.headers["Location"] = "/?instagram_connected=pending_verification"
    return response



@router.post("/refresh")
async def refresh_instagram_token(x_nova_api_key: str | None = Header(default=None)):
    """Refresh the stored long-lived token under a cross-worker PostgreSQL lock."""
    import hmac

    expected_key = os.getenv("NOVA_API_KEY", "").strip()
    if not expected_key:
        raise HTTPException(status_code=503, detail="NOVA_API_KEY is not configured.")
    if not x_nova_api_key or not hmac.compare_digest(x_nova_api_key, expected_key):
        raise HTTPException(status_code=401, detail="Missing or invalid X-NOVA-API-Key.")

    try:
        with instagram_refresh_lock():
            return await _refresh_instagram_token_locked()
    except InstagramRefreshInProgress:
        raise HTTPException(
            status_code=409,
            detail="An Instagram token refresh is already in progress. Retry after it finishes.",
        ) from None
    except (OAuthStoreError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Instagram refresh coordination is unavailable. Retry after database connectivity is restored.",
        ) from None


async def _refresh_instagram_token_locked():
    """Perform token refresh while the shared PostgreSQL advisory lock is held."""
    try:
        stored = load_latest_instagram_token()
    except (OAuthStoreError, OAuthSecurityError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Instagram token storage is unavailable or cannot decrypt the stored token.",
        ) from None
    if not stored:
        raise HTTPException(status_code=404, detail="No OAuth-connected Instagram account was found.")
    if not isinstance(stored, dict):
        raise HTTPException(status_code=503, detail="Stored Instagram credentials are malformed. Reconnect Instagram.")

    token = stored.get("access_token")
    user_id = stored.get("instagram_user_id")
    if not isinstance(token, str) or not token.strip() or not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=503, detail="Stored Instagram credentials are incomplete. Reconnect Instagram.")

    expires_at = stored.get("expires_at")
    now = datetime.now(timezone.utc)
    if expires_at is not None:
        if not isinstance(expires_at, datetime) or expires_at.tzinfo is None:
            raise HTTPException(status_code=503, detail="Stored Instagram token expiry is invalid. Reconnect Instagram.")
        if expires_at <= now:
            raise HTTPException(status_code=409, detail="The stored token has expired. Reconnect Instagram instead of trying to refresh it.")

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://graph.instagram.com/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": token,
                },
            )
        if response.is_error:
            if response.status_code in (400, 401, 403):
                raise HTTPException(
                    status_code=409,
                    detail="Instagram rejected the stored token. Reconnect Instagram and authorize the account again.",
                )
            if response.status_code == 429:
                raise HTTPException(
                    status_code=503,
                    detail="Instagram temporarily rate-limited token refresh. Try again later.",
                )
            raise HTTPException(
                status_code=502,
                detail="Instagram token refresh failed because the provider is temporarily unavailable. Try again later.",
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Instagram returned an invalid token-refresh response.")
        refreshed_token = payload.get("access_token")
        if not isinstance(refreshed_token, str) or not refreshed_token.strip():
            raise HTTPException(status_code=502, detail="Instagram did not return a refreshed token.")
        expires_in = payload.get("expires_in")
        refreshed_expiry = token_expiry_from_seconds(expires_in, fallback=expires_at)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError, OverflowError):
        raise HTTPException(
            status_code=502,
            detail="Instagram token refresh could not be completed. Try again later; credentials were not returned.",
        ) from None

    try:
        save_instagram_token(user_id, refreshed_token, expires_at=refreshed_expiry)
    except (OAuthStoreError, OAuthSecurityError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Instagram returned a refreshed token but NOVA could not save it securely. Check database and encryption-key configuration before retrying.",
        ) from None

    return {
        "status": "refreshed",
        "instagram_user_id": user_id,
        "expires_at": refreshed_expiry.isoformat() if refreshed_expiry else None,
        "token_returned": False,
    }
