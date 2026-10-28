"""Server-side Instagram Login OAuth routes.

Configure the Instagram Login product in Meta and register the exact HTTPS
callback URL before enabling these routes in production.
"""
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.oauth_security import OAuthSecurityError, create_oauth_state, validate_oauth_state
from app.oauth_store import (
    OAuthStoreError,
    consume_oauth_state,
    save_instagram_token,
    save_oauth_state,
)

router = APIRouter(prefix="/oauth/instagram", tags=["Instagram OAuth"])
STATE_COOKIE = "nova_instagram_oauth_state"
STATE_MAX_AGE_SECONDS = 600
DEFAULT_SCOPES = "instagram_business_basic"


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
            short_token = short_payload.get("access_token")
            user_id = str(short_payload.get("user_id", "")).strip()
            if not short_token or not user_id:
                raise HTTPException(status_code=502, detail="Instagram did not return the expected authorization response.")

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
            long_token = long_payload.get("access_token")
            if not long_token:
                raise HTTPException(status_code=502, detail="Instagram did not return a long-lived access token.")
            expires_in = long_payload.get("expires_in")
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                if isinstance(expires_in, (int, float)) and expires_in > 0
                else None
            )
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
