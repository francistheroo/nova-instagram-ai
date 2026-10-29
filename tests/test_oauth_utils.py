from datetime import datetime, timedelta, timezone

import pytest

from app.oauth_utils import MAX_TOKEN_LIFETIME_SECONDS, token_expiry_from_seconds


def test_token_expiry_converts_integer_seconds_to_aware_utc():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = token_expiry_from_seconds(3600, now=now)
    assert result == now + timedelta(hours=1)
    assert result.tzinfo == timezone.utc


def test_token_expiry_accepts_fractional_seconds_and_rounds_down():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert token_expiry_from_seconds(3600.9, now=now) == now + timedelta(hours=1)


def test_token_expiry_accepts_maximum_supported_lifetime():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert token_expiry_from_seconds(MAX_TOKEN_LIFETIME_SECONDS, now=now) == (
        now + timedelta(seconds=MAX_TOKEN_LIFETIME_SECONDS)
    )


def test_missing_expiry_returns_none():
    assert token_expiry_from_seconds(None) is None


def test_missing_expiry_preserves_aware_fallback_as_utc():
    fallback = datetime(2030, 1, 1, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert token_expiry_from_seconds(None, fallback=fallback) == fallback.astimezone(timezone.utc)


def test_missing_expiry_rejects_naive_fallback():
    with pytest.raises(ValueError, match="fallback expiry must be timezone-aware"):
        token_expiry_from_seconds(None, fallback=datetime(2030, 1, 1))


def test_expiry_rejects_naive_current_time():
    with pytest.raises(ValueError, match="current time must be timezone-aware"):
        token_expiry_from_seconds(60, now=datetime(2030, 1, 1))


@pytest.mark.parametrize(
    "expires_in",
    [
        True,
        False,
        0,
        -1,
        -0.5,
        0.5,
        "3600",
        [],
        {},
        float("nan"),
        float("inf"),
        float("-inf"),
        MAX_TOKEN_LIFETIME_SECONDS + 1,
        10**100,
    ],
)
def test_expiry_rejects_malformed_or_unsafe_provider_values(expires_in):
    with pytest.raises(ValueError):
        token_expiry_from_seconds(expires_in)
