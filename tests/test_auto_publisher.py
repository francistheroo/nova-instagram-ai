from datetime import date, datetime
from zoneinfo import ZoneInfo

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



def test_previous_minute_slot_uses_previous_local_date_at_midnight():
    now = datetime(2026, 10, 31, 0, 0, 15, tzinfo=ZoneInfo("Asia/Kolkata"))

    slots = publisher._due_local_slots(now)

    assert slots["00:00"] == date(2026, 10, 31)
    assert slots["23:59"] == date(2026, 10, 30)


def test_current_and_previous_schedule_slots_keep_their_local_date():
    now = datetime(2026, 10, 31, 18, 30, 45, tzinfo=ZoneInfo("Asia/Kolkata"))

    slots = publisher._due_local_slots(now)

    assert slots == {
        "18:30": date(2026, 10, 31),
        "18:29": date(2026, 10, 31),
    }



def test_schedule_times_accept_only_unique_valid_local_time_slots():
    assert publisher._schedule_times(
        ["09:00", "9:00", "24:00", "12:60", "13:15", "09:00", None],
        ["08:00"],
    ) == ["09:00", "13:15"]


def test_malformed_schedule_times_disable_schedule_instead_of_iterating_characters():
    assert publisher._schedule_times("09:00", ["09:00"]) == []
    assert publisher._schedule_times({"time": "09:00"}, ["09:00"]) == []


def test_daily_limit_rejects_booleans_negative_values_and_unbounded_caps():
    assert publisher._daily_limit(3, 3) == 3
    assert publisher._daily_limit(None, 4) == 4
    assert publisher._daily_limit(True, 3) == 0
    assert publisher._daily_limit(-1, 3) == 0
    assert publisher._daily_limit(21, 3) == 0
    assert publisher._daily_limit("3", 3) == 0
