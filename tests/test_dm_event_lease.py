"""Tests for safe reclamation of abandoned DM-event processing leases."""
import app.dm_memory as dm_memory


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.sql = ""
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return FakeResult(self.row)


def test_claim_dm_event_allows_database_to_reclaim_expired_processing_lease(monkeypatch):
    connection = FakeConnection({"message_id": "mid.lease.1"})
    monkeypatch.setattr(dm_memory, "_connect", lambda: connection)

    assert dm_memory.claim_dm_event("mid.lease.1") is True
    normalized_sql = " ".join(connection.sql.split())
    assert "status = 'retryable'" in normalized_sql
    assert "status = 'processing'" in normalized_sql
    assert "lease_until <= %s" in normalized_sql
    # The same current timestamp is used to establish the new lease and
    # determine whether the previous processing lease has expired.
    assert connection.params[0] == "mid.lease.1"
    assert connection.params[1] > connection.params[2]


def test_claim_dm_event_returns_false_when_database_does_not_claim_event(monkeypatch):
    connection = FakeConnection(None)
    monkeypatch.setattr(dm_memory, "_connect", lambda: connection)

    assert dm_memory.claim_dm_event("mid.active.1") is False
