import pytest


@pytest.fixture(autouse=True)
def preserve_existing_webhook_test_master_state(request, monkeypatch):
    """Existing webhook tests explicitly opt into DM auto-replies via env flags."""
    node_id = request.node.nodeid
    if "webhook" in node_id and "master_switch" not in node_id:
        import app.instagram_webhook as webhook_module
        monkeypatch.setattr(webhook_module, "master_enabled", lambda: True)
        monkeypatch.setattr(webhook_module, "mark_dm_event_sending", lambda _message_id: None)
        # Most webhook tests focus on event processing and explicitly enable the
        # feature flag. Keep the global kill switch enabled for those tests;
        # dedicated automation_switch tests override it to verify fail-closed behavior.
        if "automation_switch" not in node_id:
            monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
