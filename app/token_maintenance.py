"""Background maintenance for OAuth-connected Instagram tokens.

The loop refreshes only tokens with a known, timezone-aware expiry that are
approaching expiry. The caller supplies a refresh callback that must use the
shared PostgreSQL refresh lock.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Callable


async def refresh_token_if_due(
    load_token: Callable,
    refresh_token: Callable,
    *,
    now: datetime | None = None,
    refresh_window: timedelta = timedelta(days=7),
    on_error: Callable[[str], None] | None = None,
) -> bool:
    """Refresh a stored token inside the configured renewal window."""
    try:
        stored = await asyncio.to_thread(load_token)
        if not isinstance(stored, dict):
            return False
        expires_at = stored.get("expires_at")
        if not isinstance(expires_at, datetime) or expires_at.tzinfo is None:
            return False
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        remaining = expires_at - current.astimezone(timezone.utc)
        if remaining <= timedelta(0) or remaining > refresh_window:
            return False
        await refresh_token()
        return True
    except Exception as exc:
        if on_error is not None:
            # Expose only a stable error class, never provider/database details.
            on_error(type(exc).__name__)
        return False


async def token_refresh_loop(
    stop_event: asyncio.Event,
    load_token: Callable,
    refresh_token: Callable,
    *,
    interval_seconds: int = 21600,
    refresh_window: timedelta = timedelta(days=7),
    on_error: Callable[[str], None] | None = None,
) -> None:
    """Periodically check whether the stored OAuth token needs refreshing."""
    while not stop_event.is_set():
        await refresh_token_if_due(
            load_token,
            refresh_token,
            refresh_window=refresh_window,
            on_error=on_error,
        )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
