from datetime import date

import app.auto_publisher as publisher


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, count, inserted_id=17):
        self.count = count
        self.inserted_id = inserted_id
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT COUNT(*)"):
            return FakeResult((self.count,))
        if normalized.startswith("INSERT INTO nova_auto_publish_runs"):
            return FakeResult((self.inserted_id,))
        return FakeResult(None)


def test_processing_slots_reserve_daily_publish_capacity(monkeypatch):
    connection = FakeConnection(count=2)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setattr(publisher.psycopg, "connect", lambda *args, **kwargs: connection)

    run_id = publisher._claim_slot(date(2026, 10, 30), "post", "18:00", 3)

    assert run_id == 17
    count_sql = " ".join(connection.statements[1][0].split())
    assert "status IN ('processing','published')" in count_sql


def test_daily_limit_blocks_new_slot_when_processing_and_published_fill_cap(monkeypatch):
    connection = FakeConnection(count=3)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setattr(publisher.psycopg, "connect", lambda *args, **kwargs: connection)

    run_id = publisher._claim_slot(date(2026, 10, 30), "post", "18:30", 3)

    assert run_id is False
    assert not any("INSERT INTO nova_auto_publish_runs" in sql for sql, _ in connection.statements)
