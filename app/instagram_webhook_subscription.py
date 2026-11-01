"""Instagram Login account-level webhook subscription helpers."""
import os
import re

import httpx
import psycopg
from fastapi import HTTPException

from app.oauth_store import (
    OAuthStoreError,
    InstagramRefreshInProgress,
    load_latest_instagram_token,
    instagram_refresh_lock,
)
from app.oauth_security import OAuthSecurityError

WEBHOOK_FIELDS = ("messages",)


def _require_webhook_api_key(x_nova_api_key: str | None) -> None:
    import hmac

    expected = os.getenv("NOVA_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="NOVA_API_KEY is not configured.")
    if not x_nova_api_key or not hmac.compare_digest(x_nova_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-NOVA-API-Key.")


def _load_subscription_credentials() -> tuple[str, str]:
    try:
        stored = load_latest_instagram_token()
    except (OAuthStoreError, OAuthSecurityError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Instagram token storage is unavailable.") from None
    if not isinstance(stored, dict):
        raise HTTPException(status_code=404, detail="No OAuth-connected Instagram account was found.")
    token = stored.get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(status_code=503, detail="Stored Instagram credentials are incomplete. Reconnect Instagram.")
    version = os.getenv("META_API_VERSION", "v25.0").strip("/")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+", version):
        raise HTTPException(status_code=503, detail="META_API_VERSION is invalid.")
    return token, version


async def update_instagram_webhook_subscription(*, subscribe: bool) -> dict:
    """Subscribe/unsubscribe only the supported messages field for the stored account."""
    method = "POST" if subscribe else "DELETE"
    params = {"subscribed_fields": ",".join(WEBHOOK_FIELDS)} if subscribe else {}
    try:
        # Serialize against token refresh so a token cannot rotate mid-request.
        with instagram_refresh_lock():
            token, version = _load_subscription_credentials()
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.request(
                    method,
                    f"https://graph.instagram.com/{version}/me/subscribed_apps",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
        if response.is_error:
            if response.status_code in (400, 401, 403):
                raise HTTPException(
                    status_code=409,
                    detail="Instagram rejected the subscription. Reconnect the account and confirm messaging permission is granted.",
                )
            if response.status_code == 429:
                raise HTTPException(status_code=503, detail="Instagram rate-limited the subscription request. Try again later.")
            raise HTTPException(status_code=502, detail="Instagram webhook subscription could not be updated.")
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("success") not in (True, "true"):
            raise HTTPException(status_code=502, detail="Instagram did not confirm the webhook subscription update.")
        return {
            "status": "subscribed" if subscribe else "unsubscribed",
            "fields": list(WEBHOOK_FIELDS) if subscribe else [],
            "account_token_exposed": False,
        }
    except HTTPException:
        raise
    except InstagramRefreshInProgress:
        raise HTTPException(status_code=409, detail="An Instagram token refresh is already in progress. Retry shortly.") from None
    except (OAuthStoreError, OAuthSecurityError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Instagram refresh coordination is unavailable.") from None
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(status_code=502, detail="Instagram webhook subscription request failed. Try again later.") from None


async def get_instagram_webhook_subscription() -> dict:
    """Read account-level subscribed fields without returning credentials."""
    try:
        with instagram_refresh_lock():
            token, version = _load_subscription_credentials()
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"https://graph.instagram.com/{version}/me/subscribed_apps",
                    headers={"Authorization": f"Bearer {token}"},
                )
        if response.is_error:
            if response.status_code in (400, 401, 403):
                raise HTTPException(status_code=409, detail="Instagram rejected the subscription status request. Reconnect the account.")
            if response.status_code == 429:
                raise HTTPException(status_code=503, detail="Instagram rate-limited the status request. Try again later.")
            raise HTTPException(status_code=502, detail="Instagram webhook subscription status is unavailable.")
        payload = response.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Instagram returned an invalid subscription status.")
        records = payload.get("data", [])
        if not isinstance(records, list):
            raise HTTPException(status_code=502, detail="Instagram returned an invalid subscription status.")
        fields: set[str] = set()
        for record in records:
            if isinstance(record, dict):
                subscribed = record.get("subscribed_fields", [])
                if isinstance(subscribed, list):
                    fields.update(field for field in subscribed if isinstance(field, str))
        return {
            "status": "subscribed" if set(WEBHOOK_FIELDS).issubset(fields) else "not_subscribed",
            "fields": sorted(fields),
            "required_fields": list(WEBHOOK_FIELDS),
            "account_token_exposed": False,
        }
    except HTTPException:
        raise
    except InstagramRefreshInProgress:
        raise HTTPException(status_code=409, detail="An Instagram token refresh is already in progress. Retry shortly.") from None
    except (OAuthStoreError, OAuthSecurityError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Instagram refresh coordination is unavailable.") from None
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(status_code=502, detail="Instagram webhook subscription status request failed.") from None
