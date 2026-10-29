"""PostgreSQL-backed regression tests for DM retry/idempotency state.

GitHub Actions supplies TEST_DATABASE_URL from an ephemeral PostgreSQL service.
When running locally without that variable, these integration tests are skipped.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from app import dm_memory


@pytest.fixture
def postgres_db(monkeypatch):
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    monkeypatch.setenv("DATABASE_URL", database_url)
    dm_memory.initialize_schema()
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "TRUNCATE TABLE nova_instagram_dm_events, nova_instagram_dm_memory RESTART IDENTITY"
        )
    return database_url


def test_database_schema_initialization_is_repeatable(postgres_db):
    dm_memory.initialize_schema()
    dm_memory.initialize_schema()


def test_only_one_concurrent_worker_claims_a_new_event(postgres_db):
    message_id = "integration.concurrent.claim"

    def claim(_):
        return dm_memory.claim_dm_event(message_id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, range(8)))

    assert results.count(True) == 1
    assert results.count(False) == 7


def test_retryable_event_can_be_reclaimed_but_sent_event_cannot(postgres_db):
    message_id = "integration.retry.state"

    assert dm_memory.claim_dm_event(message_id) is True
    assert dm_memory.claim_dm_event(message_id) is False

    dm_memory.finish_dm_event(message_id, "retryable")
    assert dm_memory.claim_dm_event(message_id) is True

    dm_memory.finish_dm_event(message_id, "sent")
    assert dm_memory.claim_dm_event(message_id) is False


def test_expired_processing_lease_can_be_reclaimed(postgres_db):
    message_id = "integration.expired.lease"
    assert dm_memory.claim_dm_event(message_id) is True

    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    with psycopg.connect(postgres_db) as conn:
        conn.execute(
            "UPDATE nova_instagram_dm_events SET lease_until = %s WHERE message_id = %s",
            (expired, message_id),
        )

    assert dm_memory.claim_dm_event(message_id) is True


def test_ignored_event_is_terminal(postgres_db):
    message_id = "integration.ignored.state"
    assert dm_memory.claim_dm_event(message_id) is True
    dm_memory.finish_dm_event(message_id, "ignored")
    assert dm_memory.claim_dm_event(message_id) is False


def test_memory_message_id_is_unique_in_postgres(postgres_db):
    first = dm_memory.store_dm_message(
        "12345", "user", "Hello NOVA", message_id="integration.memory.unique"
    )
    duplicate = dm_memory.store_dm_message(
        "12345", "user", "Hello NOVA", message_id="integration.memory.unique"
    )

    assert first is not None
    assert duplicate is None
    with psycopg.connect(postgres_db) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM nova_instagram_dm_memory WHERE message_id = %s",
            ("integration.memory.unique",),
        ).fetchone()
    assert row[0] == 1


def test_message_memory_expiry_is_twelve_hours(postgres_db):
    before = datetime.now(timezone.utc)
    expiry = dm_memory.store_dm_message("12345", "user", "Hello NOVA")
    after = datetime.now(timezone.utc)

    assert expiry is not None
    assert before + timedelta(hours=12) <= expiry <= after + timedelta(hours=12)


def test_expired_memory_row_is_removed_before_reinserting_message_id(postgres_db):
    message_id = "integration.expired.memory"
    assert dm_memory.store_dm_message(
        "12345", "user", "First delivery", message_id=message_id
    ) is not None

    with psycopg.connect(postgres_db) as conn:
        conn.execute(
            "UPDATE nova_instagram_dm_memory SET expires_at = %s WHERE message_id = %s",
            (datetime.now(timezone.utc) - timedelta(seconds=1), message_id),
        )

    replacement = dm_memory.store_dm_message(
        "12345", "user", "Replacement after expiry", message_id=message_id
    )
    assert replacement is not None


@pytest.mark.parametrize("message_id", [None, "", "x" * 513, 123, []])
def test_claim_rejects_invalid_message_ids_before_database_access(postgres_db, message_id):
    with pytest.raises(ValueError, match="invalid Meta message ID"):
        dm_memory.claim_dm_event(message_id)


@pytest.mark.parametrize("message_id", ["", "x" * 513, 123, []])
def test_memory_store_rejects_invalid_message_ids_before_database_access(postgres_db, message_id):
    with pytest.raises(ValueError, match="invalid Meta message ID"):
        dm_memory.store_dm_message("12345", "user", "Hello", message_id=message_id)


def test_finish_rejects_invalid_state_and_message_id_before_database_access(postgres_db):
    with pytest.raises(ValueError, match="status must be sent, retryable, or ignored"):
        dm_memory.finish_dm_event("integration.bad-status", "processing")

    with pytest.raises(ValueError, match="invalid Meta message ID"):
        dm_memory.finish_dm_event("", "sent")
