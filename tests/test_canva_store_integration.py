"""PostgreSQL integration tests for Canva token integrity and account isolation."""
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from cryptography.fernet import Fernet

from app import canva_store
from app.canva_store import CanvaStoreError
from app.oauth_security import OAuthSecurityError, encrypt_access_token


@pytest.fixture
def canva_db(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", key)
    monkeypatch.delenv("CANVA_ACCOUNT_KEY", raising=False)
    canva_store.initialize_canva_schema()
    with psycopg.connect(url) as conn:
        conn.execute("TRUNCATE TABLE nova_canva_tokens")
    return {"url": url, "key": key}


def _bundle(user_id, access_token, refresh_token=None):
    value = {"user_id": user_id, "access_token": access_token}
    if refresh_token is not None:
        value["refresh_token"] = refresh_token
    return value


def test_account_load_is_explicit_and_never_falls_back_to_another_account(canva_db, monkeypatch):
    first_key = "canva-user-a-" + secrets.token_urlsafe(8)
    second_key = "canva-user-b-" + secrets.token_urlsafe(8)
    canva_store.save_canva_tokens(_bundle(first_key, "access-a", "refresh-a"), expires_at=None)
    canva_store.save_canva_tokens(_bundle(second_key, "access-b", "refresh-b"), expires_at=None)

    assert canva_store.load_canva_tokens(first_key)["access_token"] == "access-a"
    assert canva_store.load_canva_tokens(second_key)["access_token"] == "access-b"

    with pytest.raises(CanvaStoreError, match="Multiple Canva accounts"):
        canva_store.load_latest_canva_tokens()

    monkeypatch.setenv("CANVA_ACCOUNT_KEY", first_key)
    selected = canva_store.load_latest_canva_tokens()
    assert selected["user_id"] == first_key
    assert selected["access_token"] == "access-a"
    assert selected["refresh_token"] == "refresh-a"


def test_missing_selected_account_does_not_fall_back_to_a_different_account(canva_db, monkeypatch):
    existing_key = "canva-user-existing-" + secrets.token_urlsafe(8)
    canva_store.save_canva_tokens(_bundle(existing_key, "existing-access"), expires_at=None)
    monkeypatch.setenv("CANVA_ACCOUNT_KEY", "canva-user-not-connected")

    assert canva_store.load_latest_canva_tokens() is None


def test_token_bundle_must_match_database_account_key(canva_db):
    database_key = "canva-account-expected-" + secrets.token_urlsafe(8)
    encrypted = encrypt_access_token(
        json.dumps({"user_id": "canva-account-other", "access_token": "private-access"}, separators=(",", ":"))
    )
    with psycopg.connect(canva_db["url"]) as conn:
        conn.execute(
            "INSERT INTO nova_canva_tokens (account_key, encrypted_token_bundle, expires_at) VALUES (%s, %s, NULL)",
            (database_key, encrypted),
        )

    with pytest.raises(CanvaStoreError, match="does not match"):
        canva_store.load_canva_tokens(database_key)


def test_non_object_or_missing_token_payload_is_rejected(canva_db):
    database_key = "canva-account-malformed-" + secrets.token_urlsafe(8)
    with psycopg.connect(canva_db["url"]) as conn:
        conn.execute(
            "INSERT INTO nova_canva_tokens (account_key, encrypted_token_bundle, expires_at) VALUES (%s, %s, NULL)",
            (database_key, encrypt_access_token(json.dumps(["not", "an", "object"]))),
        )

    with pytest.raises(CanvaStoreError, match="malformed"):
        canva_store.load_canva_tokens(database_key)


def test_wrong_encryption_key_fails_safely_and_correct_key_restores_access(canva_db, monkeypatch):
    account_key = "canva-key-recovery-" + secrets.token_urlsafe(8)
    canva_store.save_canva_tokens(_bundle(account_key, "protected-access"), expires_at=None)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))

    with pytest.raises(CanvaStoreError, match="decrypted"):
        canva_store.load_canva_tokens(account_key)

    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", canva_db["key"])
    loaded = canva_store.load_canva_tokens(account_key)
    assert loaded is not None
    assert loaded["access_token"] == "protected-access"


def test_missing_encryption_key_does_not_overwrite_saved_token(canva_db, monkeypatch):
    account_key = "canva-missing-key-" + secrets.token_urlsafe(8)
    canva_store.save_canva_tokens(_bundle(account_key, "old-access", "old-refresh"), expires_at=None)
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)

    with pytest.raises(OAuthSecurityError):
        canva_store.save_canva_tokens(_bundle(account_key, "new-access", "new-refresh"), expires_at=None)

    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", canva_db["key"])
    old = canva_store.load_canva_tokens(account_key)
    assert old is not None
    assert old["access_token"] == "old-access"
    assert old["refresh_token"] == "old-refresh"


def test_failed_database_update_preserves_existing_credentials(canva_db):
    account_key = "canva-atomic-update-" + secrets.token_urlsafe(8)
    canva_store.save_canva_tokens(_bundle(account_key, "old-access", "old-refresh"), expires_at=None)
    trigger_name = "nova_canva_test_reject_update"
    function_name = "nova_canva_test_reject_update_fn"

    with psycopg.connect(canva_db["url"]) as conn:
        conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON nova_canva_tokens")
        conn.execute(f"DROP FUNCTION IF EXISTS {function_name}()")
        conn.execute(f"""
            CREATE FUNCTION {function_name}() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.account_key = '{account_key}' THEN
                    RAISE EXCEPTION 'simulated token write failure';
                END IF;
                RETURN NEW;
            END;
            $$
        """)
        conn.execute(
            f"CREATE TRIGGER {trigger_name} BEFORE UPDATE ON nova_canva_tokens "
            f"FOR EACH ROW EXECUTE FUNCTION {function_name}()"
        )

    try:
        with pytest.raises(psycopg.Error, match="simulated token write failure"):
            canva_store.save_canva_tokens(_bundle(account_key, "new-access", "new-refresh"), expires_at=None)
        still_saved = canva_store.load_canva_tokens(account_key)
        assert still_saved is not None
        assert still_saved["access_token"] == "old-access"
        assert still_saved["refresh_token"] == "old-refresh"
    finally:
        with psycopg.connect(canva_db["url"]) as conn:
            conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON nova_canva_tokens")
            conn.execute(f"DROP FUNCTION IF EXISTS {function_name}()")


def test_database_expiry_column_is_authoritative(canva_db):
    account_key = "canva-expiry-authority-" + secrets.token_urlsafe(8)
    expected_expiry = datetime.now(timezone.utc) + timedelta(hours=3)
    bundle = _bundle(account_key, "expiry-access")
    bundle["expires_at"] = "untrusted-bundle-value"
    canva_store.save_canva_tokens(bundle, expires_at=expected_expiry)

    loaded = canva_store.load_canva_tokens(account_key)
    assert loaded is not None
    assert loaded["expires_at"] == expected_expiry
