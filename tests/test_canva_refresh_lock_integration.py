"""Integration tests for the cross-worker Canva refresh advisory lock.

GitHub Actions sets TEST_DATABASE_URL to an ephemeral PostgreSQL service.
"""
import os

import pytest

from app import canva_store
from app.canva_store import CanvaRefreshInProgress, CanvaStoreError


@pytest.fixture
def postgres_database(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def test_refresh_lock_is_exclusive_across_postgres_sessions(postgres_database):
    # Each lock context owns its own database connection. The second attempt
    # must fail fast rather than sending a second refresh with the same token.
    with canva_store.canva_refresh_lock():
        with pytest.raises(CanvaRefreshInProgress):
            with canva_store.canva_refresh_lock():
                pytest.fail("A second session must not acquire the refresh lock")


def test_refresh_lock_can_be_reacquired_after_normal_exit(postgres_database):
    with canva_store.canva_refresh_lock():
        pass

    # Success proves that the prior session released its lock.
    with canva_store.canva_refresh_lock():
        pass


def test_refresh_lock_is_released_when_refresh_raises(postgres_database):
    with pytest.raises(RuntimeError, match="simulated failure"):
        with canva_store.canva_refresh_lock():
            raise RuntimeError("simulated failure")

    with canva_store.canva_refresh_lock():
        pass


def test_refresh_lock_requires_shared_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(CanvaStoreError, match="DATABASE_URL"):
        with canva_store.canva_refresh_lock():
            pytest.fail("A distributed lock must not silently degrade to an in-process lock")
