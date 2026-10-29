"""Validation helpers for expiry values returned by external OAuth providers."""
import math
from datetime import datetime, timedelta, timezone
from typing import Any

# OAuth access tokens should not plausibly be valid for decades. This bound
# also protects datetime arithmetic from malformed or unexpectedly huge values.
MAX_TOKEN_LIFETIME_SECONDS = 10 * 365 * 24 * 60 * 60


def token_expiry_from_seconds(
    expires_in: Any,
    *,
    fallback: datetime | None = None,
    now: datetime | None = None,
) -> datetime | None:
    """Convert a provider's expires_in value into an aware UTC timestamp.

    Missing values preserve an explicit fallback (useful during refresh); malformed
    provided values are rejected instead of accidentally storing a non-expiring token.
    """
    if expires_in is None:
        if fallback is not None and fallback.tzinfo is None:
            raise ValueError("fallback expiry must be timezone-aware")
        return fallback.astimezone(timezone.utc) if fallback is not None else None

    if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
        raise ValueError("provider returned an invalid token expiry")
    if expires_in <= 0 or expires_in > MAX_TOKEN_LIFETIME_SECONDS:
        raise ValueError("provider returned an out-of-range token expiry")
    if isinstance(expires_in, float) and not math.isfinite(expires_in):
        raise ValueError("provider returned a non-finite token expiry")

    seconds = int(expires_in)
    if seconds < 1:
        raise ValueError("provider returned a token expiry below one second")

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("current time must be timezone-aware")
    try:
        return current.astimezone(timezone.utc) + timedelta(seconds=seconds)
    except (OverflowError, ValueError) as exc:
        raise ValueError("provider returned an out-of-range token expiry") from exc
