import asyncio

import app.auto_publisher as auto_publisher
import app.main as main


def _clear_scheduler_state():
    for name in ("nova_scheduler_stop", "nova_scheduler_task", "nova_scheduler_error", "nova_scheduler_timezone_valid"):
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
    assert health["auto_scheduler_timezone_valid"] is True
    assert health["auto_scheduler_ready"] is False
    _clear_scheduler_state()


def test_scheduler_health_reports_active_task(monkeypatch):
    _clear_scheduler_state()
    monkeypatch.setenv("NOVA_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setattr(auto_publisher, "initialize_scheduler_schema", lambda: None)

    async def idle_scheduler(_meta_request, _instagram_config, stop_event, _timezone):
        await stop_event.wait()

    monkeypatch.setattr(main, "scheduler_loop", idle_scheduler)

    async def run_start_and_stop():
        await main.start_auto_publisher()
        health = await main.health()
        assert health["auto_scheduler_running"] is True
        assert health["auto_scheduler_error"] is None
        assert health["auto_scheduler_timezone_valid"] is True
        assert health["auto_scheduler_ready"] is True
        ready = await main.readiness()
        assert ready["status"] == "ready"
        await main.stop_auto_publisher()
        assert main.app.state.nova_scheduler_task.done()

    asyncio.run(run_start_and_stop())
    _clear_scheduler_state()



def test_invalid_timezone_fails_startup_and_readiness_without_initializing_scheduler(monkeypatch):
    _clear_scheduler_state()
    monkeypatch.setenv("NOVA_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setenv("NOVA_TIMEZONE", "Invalid/Timezone")

    def should_not_initialize():
        raise AssertionError("scheduler schema must not initialize with invalid timezone")

    monkeypatch.setattr(auto_publisher, "initialize_scheduler_schema", should_not_initialize)

    asyncio.run(main.start_auto_publisher())

    assert main.app.state.nova_scheduler_error == "invalid_timezone"
    assert main.app.state.nova_scheduler_timezone_valid is False
    assert not hasattr(main.app.state, "nova_scheduler_task")

    health = asyncio.run(main.health())
    assert health["auto_scheduler_ready"] is False
    assert health["auto_scheduler_timezone_valid"] is False
    assert health["auto_scheduler_error"] == "invalid_timezone"

    try:
        asyncio.run(main.readiness())
    except main.HTTPException as exc:
        assert exc.status_code == 503
        assert exc.detail["auto_scheduler_error"] == "invalid_timezone"
    else:
        raise AssertionError("/ready must fail for invalid scheduler timezone")
    _clear_scheduler_state()


def test_readiness_is_healthy_when_scheduler_is_intentionally_disabled(monkeypatch):
    monkeypatch.setenv("NOVA_SCHEDULER_ENABLED", "false")

    ready = asyncio.run(main.readiness())

    assert ready == {
        "status": "ready",
        "auto_scheduler_enabled": False,
        "auto_scheduler_ready": True,
    }
