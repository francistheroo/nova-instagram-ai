import asyncio

import app.auto_publisher as auto_publisher
import app.main as main


def _clear_scheduler_state():
    for name in ("nova_scheduler_stop", "nova_scheduler_task", "nova_scheduler_error"):
        if hasattr(main.app.state, name):
            delattr(main.app.state, name)


def test_scheduler_does_not_start_without_database_and_health_reports_error(monkeypatch):
    _clear_scheduler_state()
    monkeypatch.setenv("NOVA_SCHEDULER_ENABLED", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def should_not_initialize():
        raise AssertionError("scheduler schema must not initialize without a database")

    monkeypatch.setattr(auto_publisher, "initialize_scheduler_schema", should_not_initialize)

    asyncio.run(main.start_auto_publisher())

    assert main.app.state.nova_scheduler_error == "database_not_configured"
    assert not hasattr(main.app.state, "nova_scheduler_task")

    health = asyncio.run(main.health())
    assert health["auto_scheduler_running"] is False
    assert health["auto_scheduler_error"] == "database_not_configured"
    _clear_scheduler_state()


def test_scheduler_health_reports_active_task(monkeypatch):
    _clear_scheduler_state()
    monkeypatch.setenv("NOVA_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setattr(auto_publisher, "initialize_scheduler_schema", lambda: None)

    async def idle_scheduler(_meta_request, _instagram_config, stop_event):
        await stop_event.wait()

    monkeypatch.setattr(main, "scheduler_loop", idle_scheduler)

    async def run_start_and_stop():
        await main.start_auto_publisher()
        health = await main.health()
        assert health["auto_scheduler_running"] is True
        assert health["auto_scheduler_error"] is None
        await main.stop_auto_publisher()
        assert main.app.state.nova_scheduler_task.done()

    asyncio.run(run_start_and_stop())
    _clear_scheduler_state()
