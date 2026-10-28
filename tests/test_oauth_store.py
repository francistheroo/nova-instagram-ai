from datetime import datetime, timezone

import pytest

from app.oauth_store import (
    OAuthStoreError,
    _database_url,
    consume_oauth_state,
    save_instagram_token,
    save_oauth_state,
)


def test_database_url_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(OAuthStoreError, match="DATABASE_URL"):
        _database_url()


def test_legacy_postgres_url_is_normalized(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://example.invalid/db")
    assert _database_url() == "postgresql://example.invalid/db"


def test_oauth_state_requires_timezone_aware_expiry(monkeypatch):
    with pytest.raises(OAuthStoreError, match="timezone-aware"):
        save_oauth_state("nonce", expires_at=datetime(2030, 1, 1))


def test_consume_state_rejects_naive_clock(monkeypatch):
    with pytest.raises(OAuthStoreError, match="timezone-aware"):
        consume_oauth_state("nonce", now=datetime(2030, 1, 1))


def test_token_store_requires_instagram_user_id(monkeypatch):
    with pytest.raises(OAuthStoreError, match="user ID"):
        save_instagram_token(" ", "token", expires_at=None)


def test_token_store_requires_aware_expiry(monkeypatch):
    with pytest.raises(OAuthStoreError, match="timezone-aware"):
        save_instagram_token("123", "token", expires_at=datetime(2030, 1, 1))
