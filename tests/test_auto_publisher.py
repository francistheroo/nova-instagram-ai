import pytest
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
    assert "status IN ('processing','published','uncertain')" in count_sql


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



def test_uncertain_publish_outcomes_reserve_daily_capacity(monkeypatch):
    connection = FakeConnection(count=3)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setattr(publisher.psycopg, "connect", lambda *args, **kwargs: connection)

    run_id = publisher._claim_slot(date(2026, 10, 31), "post", "19:00", 3)

    assert run_id is False
    count_sql = " ".join(connection.statements[1][0].split())
    assert "status IN ('processing','published','uncertain')" in count_sql
    assert not any("INSERT INTO nova_auto_publish_runs" in sql for sql, _ in connection.statements)


def test_ambiguous_meta_publish_response_uses_uncertain_state(monkeypatch):
    import asyncio

    calls = []

    async def fake_meta_request(method, path, *, data=None, params=None):
        calls.append((method, path, data))
        if path.endswith("/media"):
            return {"id": "container-123"}
        raise TimeoutError("simulated network timeout")

    async def fake_chat_completion(*args, **kwargs):
        return ('{"image_prompt":"A calm abstract sunrise","caption":"Good morning"}', "test", "test-model")

    class FakeResponse:
        is_error = False

        def json(self):
            return {"data": [{"url": "https://images.example.test/nova.png"}]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(publisher, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(publisher.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setenv("IMAGE_API_BASE_URL", "https://images.example.test/v1")
    monkeypatch.setenv("IMAGE_API_KEY", "test-key")
    monkeypatch.setenv("IMAGE_MODEL", "test-image-model")

    with pytest.raises(publisher.PublishOutcomeUncertain):
        asyncio.run(
            publisher._generate_and_publish(
                "post",
                fake_meta_request,
                lambda: ("token", "ig-user-1", "https://graph.example.test/v25.0"),
            )
        )

    assert [call[1] for call in calls] == ["ig-user-1/media", "ig-user-1/media_publish"]
