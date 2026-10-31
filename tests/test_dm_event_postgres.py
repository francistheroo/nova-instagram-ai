"""Opt-in PostgreSQL integration tests for DM event claims.

Set NOVA_TEST_DATABASE_URL to a dedicated disposable test database to run these.
These tests never fall back to DATABASE_URL, to avoid touching application data.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from app.dm_memory import _connect, claim_dm_event, finish_dm_event, initialize_schema, mark_dm_event_sending


TEST_DATABASE_URL = os.getenv("NOVA_TEST_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set NOVA_TEST_DATABASE_URL to a dedicated test PostgreSQL database",
)


@pytest.fixture
def test_database(monkeypatch):
    # Intentionally use only the explicitly named test URL, never production DATABASE_URL.
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    initialize_schema()
    message_id = f"test.nova.{uuid.uuid4().hex}"
    try:
        yield message_id
    finally:
        with _connect() as conn:
            conn.execute(
                "DELETE FROM nova_instagram_dm_events WHERE message_id = %s",
                (message_id,),
            )
            conn.execute(
                "DELETE FROM nova_instagram_dm_memory WHERE message_id = %s",
                (message_id,),
            )


def test_only_one_concurrent_worker_claims_new_event(test_database):
    # Separate connections race on the same primary key; exactly one insert wins.
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: claim_dm_event(test_database), range(8)))

    assert results.count(True) == 1
    assert results.count(False) == 7


def test_sent_event_cannot_be_claimed_again(test_database):
    assert claim_dm_event(test_database) is True
    finish_dm_event(test_database, "sent")

    assert claim_dm_event(test_database) is False


def test_retryable_event_can_be_claimed_again(test_database):
    assert claim_dm_event(test_database) is True
    finish_dm_event(test_database, "retryable")

    assert claim_dm_event(test_database) is True
    finish_dm_event(test_database, "sent")


def test_processing_event_cannot_be_claimed_before_lease_expires(test_database):
    assert claim_dm_event(test_database) is True
    assert claim_dm_event(test_database) is False


def test_uncertain_event_is_terminal_and_not_reclaimed(test_database):
    assert claim_dm_event(test_database) is True
    finish_dm_event(test_database, "uncertain")

    assert claim_dm_event(test_database) is False


def test_sending_event_is_not_reclaimed_after_processing_lease_would_expire(test_database):
    assert claim_dm_event(test_database) is True
    mark_dm_event_sending(test_database)

    assert claim_dm_event(test_database) is False
