import asyncio
from datetime import datetime, timedelta, timezone

from app.token_maintenance import refresh_token_if_due


def test_automatic_refresh_runs_inside_seven_day_window():
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    calls = []
    result = asyncio.run(
        refresh_token_if_due(
            lambda: {"expires_at": now + timedelta(days=3)},
            lambda: _record(calls),
            now=now,
        )
    )
    assert result is True
    assert calls == ["refresh"]


def test_automatic_refresh_skips_token_outside_window():
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    calls = []
    result = asyncio.run(
        refresh_token_if_due(
            lambda: {"expires_at": now + timedelta(days=8)},
            lambda: _record(calls),
            now=now,
        )
    )
    assert result is False
    assert calls == []


def test_automatic_refresh_skips_expired_or_unknown_expiry():
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    calls = []
    for expiry in (now - timedelta(seconds=1), None, "invalid"):
        result = asyncio.run(
            refresh_token_if_due(
                lambda expiry=expiry: {"expires_at": expiry},
                lambda: _record(calls),
                now=now,
            )
        )
        assert result is False
    assert calls == []


def test_automatic_refresh_reports_safe_error_class_and_continues():
    errors = []

    def fail_load():
        raise RuntimeError("private database detail")

    result = asyncio.run(
        refresh_token_if_due(
            fail_load,
            lambda: _record([]),
            on_error=errors.append,
        )
    )
    assert result is False
    assert errors == ["RuntimeError"]


async def _record(calls):
    calls.append("refresh")
