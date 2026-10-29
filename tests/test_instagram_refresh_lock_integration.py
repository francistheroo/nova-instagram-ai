"""Integration tests for the cross-worker Instagram refresh advisory lock."""
import os

import pytest

from app import oauth_store
from app.oauth_store import InstagramRefreshInProgress, OAuthStoreError


@pytest.fixture
def postgres_database(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def test_refresh_lock_is_exclusive_across_postgres_sessions(postgres_database):
    with oauth_store.instagram_refresh_lock():
        with pytest.raises(InstagramRefreshInProgress):
            with oauth_store.instagram_refresh_lock():
                pytest.fail("A second session must not acquire the refresh lock")


def test_refresh_lock_can_be_reacquired_after_normal_exit(postgres_database):
    with oauth_store.instagram_refresh_lock():
        pass

    with oauth_store.instagram_refresh_lock():
        pass


def test_refresh_lock_is_released_when_refresh_raises(postgres_database):
    with pytest.raises(RuntimeError, match="simulated failure"):
        with oauth_store.instagram_refresh_lock():
            raise RuntimeError("simulated failure")

    with oauth_store.instagram_refresh_lock():
        pass


def test_refresh_lock_requires_shared_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(OAuthStoreError, match="lock storage is unavailable"):
        with oauth_store.instagram_refresh_lock():
            pytest.fail("A distributed lock must not degrade to an in-process lock")
