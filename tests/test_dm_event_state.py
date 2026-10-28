from contextlib import contextmanager

import pytest

import app.dm_memory as memory


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, returned_row):
        self.returned_row = returned_row
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.calls.append((query, params))
        return FakeResult(self.returned_row)


def install_connection(monkeypatch, returned_row):
    connection = FakeConnection(returned_row)

    @contextmanager
    def connect():
        yield connection

    monkeypatch.setattr(memory, "_connect", connect)
    return connection


def test_claim_dm_event_returns_true_when_database_claims_event(monkeypatch):
    connection = install_connection(monkeypatch, {"message_id": "mid.1"})

    assert memory.claim_dm_event("mid.1") is True
    query, params = connection.calls[0]
    assert "ON CONFLICT (message_id) DO UPDATE" in query
    assert "status = 'retryable'" in query
    assert params[0] == "mid.1"


def test_claim_dm_event_returns_false_when_event_is_already_claimed(monkeypatch):
    install_connection(monkeypatch, None)

    assert memory.claim_dm_event("mid.1") is False


def test_finish_dm_event_only_allows_terminal_or_retryable_status():
    with pytest.raises(ValueError):
        memory.finish_dm_event("mid.1", "processing")
