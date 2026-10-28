"""Canva Connect OAuth 2.0 Authorization Code flow with PKCE (S256)."""
import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.oauth_security import OAuthSecurityError, create_oauth_state, validate_oauth_state
from app.oauth_store import OAuthStoreError, consume_oauth_state, save_oauth_state
from app.canva_store import CanvaStoreError, save_canva_tokens

router = APIRouter(prefix="/oauth/canva", tags=["Canva OAuth"])


def _config() -> tuple[str, str, str]:
    client_id = os.getenv("CANVA_CLIENT_ID", "").strip()
    redirect_uri = os.getenv("CANVA_REDIRECT_URI", "").strip()
    client_secret = os.getenv("CANVA_CLIENT_SECRET", "").strip()
    if not client_id or not redirect_uri or not client_secret:
        raise HTTPException(status_code=503, detail="Configure CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, and CANVA_REDIRECT_URI on the server.")
    if not redirect_uri.startswith("https://"):
        raise HTTPException(status_code=503, detail="CANVA_REDIRECT_URI must use HTTPS.")
    return client_id, client_secret, redirect_uri


@router.get("/start")
async def canva_oauth_start():
    client_id, _, redirect_uri = _config()
    try:
        state = create_oauth_state()
        payload = validate_oauth_state(state)
        save_oauth_state(payload["nonce"], expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    except (OAuthSecurityError, OAuthStoreError):
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
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
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
    except OAuthStoreError:
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
        access_token = token_payload.get("access_token") if isinstance(token_payload, dict) else None
        if not access_token:
            raise HTTPException(status_code=502, detail="Canva did not return an access token.")
        expires_in = token_payload.get("expires_in")
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)) if isinstance(expires_in, (int, float)) and expires_in > 0 else None
        save_canva_tokens(token_payload, expires_at=expires_at)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError, CanvaStoreError, OAuthStoreError, OAuthSecurityError):
        raise HTTPException(status_code=502, detail="Canva connection could not be saved. Check server configuration without logging credentials.") from None

    response = RedirectResponse("/?canva_connected=pending_verification", status_code=303)
    response.delete_cookie("nova_canva_oauth_state", path="/oauth/canva")
    response.delete_cookie("nova_canva_pkce_verifier", path="/oauth/canva")
    return response
