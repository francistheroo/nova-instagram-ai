from datetime import date

import app.auto_publisher as publisher


class _Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _DuplicateSlotConnection:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.statements.append((normalized, params))
        if normalized.startswith("SELECT COUNT(*)"):
            return _Cursor((0,))
        if normalized.startswith("INSERT INTO nova_auto_publish_runs"):
            # PostgreSQL ON CONFLICT DO NOTHING returns no row for an existing slot.
            return _Cursor(None)
        return _Cursor(None)


def test_existing_schedule_slot_is_not_claimed_twice(monkeypatch):
    connection = _DuplicateSlotConnection()
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setattr(publisher.psycopg, "connect", lambda *args, **kwargs: connection)

    run_id = publisher._claim_slot(date(2026, 11, 1), "post", "09:00", 3)

    assert run_id is False
    assert "pg_advisory_xact_lock" in connection.statements[0][0]
    insert_sql = connection.statements[2][0]
    assert "ON CONFLICT (local_date,content_type,slot) DO NOTHING" in insert_sql
    assert "RETURNING id" in insert_sql
