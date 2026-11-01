import asyncio

import app.main as main
import app.token_maintenance as token_maintenance


def test_token_refresh_initializes_oauth_schema_before_starting_worker(monkeypatch):
    for name in ("instagram_token_refresh_task", "instagram_token_refresh_stop", "instagram_token_refresh_error"):
        if hasattr(main.app.state, name):
            delattr(main.app.state, name)
    monkeypatch.setenv("INSTAGRAM_TOKEN_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/nova")
    events = []

    def initialize_schema():
        events.append("schema")

    async def fake_refresh_loop(stop_event, load_token, refresh_token, **kwargs):
        events.append("worker_started")
        await stop_event.wait()

    monkeypatch.setattr(main, "initialize_oauth_schema", initialize_schema)
    monkeypatch.setattr(token_maintenance, "token_refresh_loop", fake_refresh_loop)

    async def run_startup():
        await main.start_automatic_instagram_token_refresh()
        await asyncio.sleep(0)
        stop_event = main.app.state.instagram_token_refresh_stop
        task = main.app.state.instagram_token_refresh_task
        stop_event.set()
        await task

    asyncio.run(run_startup())

    assert events == ["schema", "worker_started"]
    assert main.app.state.instagram_token_refresh_error is None


def test_token_refresh_worker_does_not_start_when_oauth_schema_initialization_fails(monkeypatch):
    for name in ("instagram_token_refresh_task", "instagram_token_refresh_stop", "instagram_token_refresh_error"):
        if hasattr(main.app.state, name):
            delattr(main.app.state, name)
    monkeypatch.setenv("INSTAGRAM_TOKEN_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/nova")
    started = []

    def fail_schema():
        raise RuntimeError("database detail must not be exposed")

    async def fake_refresh_loop(*args, **kwargs):
        started.append(True)

    monkeypatch.setattr(main, "initialize_oauth_schema", fail_schema)
    monkeypatch.setattr(token_maintenance, "token_refresh_loop", fake_refresh_loop)

    asyncio.run(main.start_automatic_instagram_token_refresh())

    assert started == []
    assert main.app.state.instagram_token_refresh_error == "schema_initialization_failed"
    assert not hasattr(main.app.state, "instagram_token_refresh_task")
