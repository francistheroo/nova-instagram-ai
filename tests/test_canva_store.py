"""Unit tests for Canva token bundle validation that do not require PostgreSQL."""
from datetime import datetime

import pytest

from app.canva_store import CanvaStoreError, save_canva_tokens


@pytest.mark.parametrize(
    "bundle",
    [
        None,
        [],
        {},
        {"access_token": ""},
        {"access_token": "   "},
        {"access_token": 123},
        {"access_token": "valid", "user_id": True},
        {"access_token": "valid", "user_id": []},
        {"access_token": "valid", "user_id": "   "},
        {"access_token": "valid", "unsupported": object()},
    ],
)
def test_save_rejects_malformed_token_bundles_before_database_access(monkeypatch, bundle):
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(CanvaStoreError):
        save_canva_tokens(bundle, expires_at=None)


@pytest.mark.parametrize(
    "expiry",
    [
        "2030-01-01T00:00:00Z",
        datetime(2030, 1, 1),
    ],
)
def test_save_rejects_invalid_expiry_before_database_access(monkeypatch, expiry):
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(CanvaStoreError, match="timezone-aware"):
        save_canva_tokens({"access_token": "valid"}, expires_at=expiry)
