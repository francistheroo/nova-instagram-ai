import pytest


@pytest.fixture(autouse=True)
def preserve_existing_webhook_test_master_state(request, monkeypatch):
    """Existing webhook tests explicitly opt into DM auto-replies via env flags."""
    node_id = request.node.nodeid
    if "webhook" in node_id and "master_switch" not in node_id:
        import app.instagram_webhook as webhook_module
        monkeypatch.setattr(webhook_module, "master_enabled", lambda: True)
