"""PostgreSQL integration tests for one-time OAuth state and encrypted tokens."""
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from cryptography.fernet import Fernet

from app import oauth_store


@pytest.fixture
def postgres_db(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    oauth_store.initialize_schema()
    return url


def test_oauth_state_can_only_be_consumed_once_across_concurrent_sessions(postgres_db):
    nonce = "integration." + secrets.token_urlsafe(32)
    oauth_store.save_oauth_state(
        nonce,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: oauth_store.consume_oauth_state(nonce), range(8)))

    assert results.count(True) == 1
    assert results.count(False) == 7
    assert oauth_store.consume_oauth_state(nonce) is False


def test_expired_oauth_state_is_rejected_and_cleaned_up(postgres_db):
    nonce = "integration.expired." + secrets.token_urlsafe(24)
    oauth_store.save_oauth_state(
        nonce,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    assert oauth_store.consume_oauth_state(nonce) is False
    assert oauth_store.consume_oauth_state(nonce) is False

    with psycopg.connect(postgres_db) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM nova_oauth_states WHERE nonce = %s",
            (nonce,),
        ).fetchone()
    assert row[0] == 0


def test_instagram_token_is_encrypted_at_rest(postgres_db):
    user_id = "integration.user." + secrets.token_urlsafe(12)
    plaintext_token = "integration-secret-" + secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    oauth_store.save_instagram_token(user_id, plaintext_token, expires_at=expiry)

    with psycopg.connect(postgres_db) as conn:
        row = conn.execute(
            "SELECT encrypted_access_token FROM nova_instagram_tokens WHERE instagram_user_id = %s",
            (user_id,),
        ).fetchone()

    assert row is not None
    assert plaintext_token not in row[0]
    assert row[0] != plaintext_token

    loaded = oauth_store.load_instagram_token(user_id)
    assert loaded is not None
    assert loaded["access_token"] == plaintext_token
    assert loaded["expires_at"] == expiry
    oauth_store.delete_instagram_token(user_id)
