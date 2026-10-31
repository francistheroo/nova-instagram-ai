import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.instagram_webhook as webhook

client = TestClient(app)


def _signature(secret: str, raw: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _post_signed_payload(monkeypatch, payload):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    raw = json.dumps(payload).encode()
    return client.post(
        "/webhooks/instagram",
        content=raw,
        headers={"X-Hub-Signature-256": _signature(secret, raw), "Content-Type": "application/json"},
    )


@pytest.mark.parametrize("payload", [
    [],
    None,
    "unexpected",
    {"entry": None},
    {"entry": "unexpected"},
    {"entry": [None, "unexpected", {}, {"messaging": "unexpected"}]},
    {"entry": [{"messaging": [None, "unexpected", {"message": "not-an-object"}]}]},
])
def test_webhook_ignores_unsupported_payload_shapes(monkeypatch, payload):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setattr(
        webhook,
        "claim_dm_event",
        lambda *_args, **_kwargs: pytest.fail("Malformed event must not claim a DM retry slot"),
    )
    monkeypatch.setattr(
        webhook,
        "store_dm_message",
        lambda *_args, **_kwargs: pytest.fail("Malformed event must not be stored"),
    )

    response = _post_signed_payload(monkeypatch, payload)

    assert response.status_code == 200
    assert response.json() == {
        "received": True,
        "stored_text_messages": 0,
        "automatic_replies_sent": 0,
        "automatic_replies_skipped": 0,
    }


def test_webhook_verification_challenge(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "verify-me")
    response = client.get(
        "/webhooks/instagram",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "12345"},
    )
    assert response.status_code == 200
    assert response.text == "12345"


def test_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    response = client.post(
        "/webhooks/instagram",
        content=b'{"entry":[]}',
        headers={"X-Hub-Signature-256": "sha256=bad"},
    )
    assert response.status_code == 401


def test_webhook_rejects_signed_malformed_json(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    raw = b'{"entry":'
    response = client.post(
        "/webhooks/instagram",
        content=raw,
        headers={"X-Hub-Signature-256": _signature(secret, raw)},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid JSON payload."


def test_webhook_storage_runtime_error_returns_service_unavailable(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")

    def unavailable(*args, **kwargs):
        raise RuntimeError("DM memory storage is unavailable.")

    monkeypatch.setattr(webhook, "store_dm_message", unavailable)
    raw = json.dumps({
        "object": "instagram",
        "entry": [{
            "messaging": [{
                "sender": {"id": "12345"},
                "message": {"mid": "test-mid-storage-error", "text": "Hello NOVA"},
            }]
        }],
    }).encode()
    response = client.post(
        "/webhooks/instagram",
        content=raw,
        headers={"X-Hub-Signature-256": _signature(secret, raw), "Content-Type": "application/json"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "DM memory storage is unavailable."


def test_webhook_stores_signed_incoming_text_only(monkeypatch):
    app_secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", app_secret)
    stored = []
    monkeypatch.setattr(webhook, "store_dm_message", lambda recipient, role, message, message_id=None: (stored.append((recipient, role, message, message_id)), "stored")[1])
    payload = {
        "object": "instagram",
        "entry": [{
            "messaging": [
                {"sender": {"id": "12345"}, "message": {"text": "Hello NOVA"}},
                {"sender": {"id": "12345"}, "message": {"text": "Echo ignored", "is_echo": True}},
                {"sender": {"id": "12345"}, "message": {"attachments": [{"type": "image"}]}},
            ]
        }]
    }
    raw = json.dumps(payload).encode()
    response = client.post(
        "/webhooks/instagram",
        content=raw,
        headers={"X-Hub-Signature-256": _signature(app_secret, raw), "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 1
    assert stored == [("12345", "user", "Hello NOVA", None)]
    assert response.json()["automatic_replies_sent"] == 0



def test_webhook_ignores_invalid_timestamp_without_generating_reply(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    finished = []
    monkeypatch.setattr(webhook, "claim_dm_event", lambda message_id: True)
    monkeypatch.setattr(webhook, "store_dm_message", lambda *args, **kwargs: "stored")
    monkeypatch.setattr(webhook, "finish_dm_event", lambda message_id, status: finished.append((message_id, status)))

    async def unexpected_generation(*args, **kwargs):
        pytest.fail("Invalid event timestamp must not generate an automatic reply")

    monkeypatch.setattr(webhook, "generate_dm_reply", unexpected_generation)
    payload = {
        "entry": [{
            "messaging": [{
                "sender": {"id": "12345"},
                "timestamp": "not-a-timestamp",
                "message": {"mid": "invalid-timestamp-mid", "text": "Hello NOVA"},
            }]
        }]
    }
    response = _post_signed_payload(monkeypatch, payload)

    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1
    assert finished == [("invalid-timestamp-mid", "ignored")]


def test_webhook_ignores_out_of_range_timestamp_without_crashing(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    finished = []
    monkeypatch.setattr(webhook, "claim_dm_event", lambda message_id: True)
    monkeypatch.setattr(webhook, "store_dm_message", lambda *args, **kwargs: "stored")
    monkeypatch.setattr(webhook, "finish_dm_event", lambda message_id, status: finished.append((message_id, status)))

    async def unexpected_generation(*args, **kwargs):
        pytest.fail("Out-of-range timestamp must not generate an automatic reply")

    monkeypatch.setattr(webhook, "generate_dm_reply", unexpected_generation)
    payload = {
        "entry": [{
            "messaging": [{
                "sender": {"id": "12345"},
                "timestamp": 10 ** 100,
                "message": {"mid": "out-of-range-timestamp-mid", "text": "Hello NOVA"},
            }]
        }]
    }
    response = _post_signed_payload(monkeypatch, payload)

    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1
    assert finished == [("out-of-range-timestamp-mid", "ignored")]


@pytest.mark.parametrize("timestamp", [float("inf"), float("-inf"), float("nan")])
def test_webhook_ignores_nonfinite_timestamp_without_crashing(monkeypatch, timestamp):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    finished = []
    monkeypatch.setattr(webhook, "claim_dm_event", lambda message_id: True)
    monkeypatch.setattr(webhook, "store_dm_message", lambda *args, **kwargs: "stored")
    monkeypatch.setattr(webhook, "finish_dm_event", lambda message_id, status: finished.append((message_id, status)))

    async def unexpected_generation(*args, **kwargs):
        pytest.fail("Non-finite timestamp must not generate an automatic reply")

    monkeypatch.setattr(webhook, "generate_dm_reply", unexpected_generation)
    payload = {
        "entry": [{
            "messaging": [{
                "sender": {"id": "12345"},
                "timestamp": timestamp,
                "message": {"mid": "nonfinite-timestamp-mid", "text": "Hello NOVA"},
            }]
        }]
    }
    response = _post_signed_payload(monkeypatch, payload)

    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1
    assert finished == [("nonfinite-timestamp-mid", "ignored")]


def test_webhook_rejects_missing_signature(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    response = client.post("/webhooks/instagram", content=b'{"entry":[]}')
    assert response.status_code == 401


def test_webhook_missing_app_secret_returns_service_unavailable(monkeypatch):
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    response = client.post(
        "/webhooks/instagram",
        content=b'{"entry":[]}',
        headers={"X-Hub-Signature-256": "sha256=anything"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "META_APP_SECRET is not configured."


def test_webhook_verification_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "expected-token")
    response = client.get(
        "/webhooks/instagram",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong-token", "hub.challenge": "12345"},
    )
    assert response.status_code == 403


def test_webhook_verification_rejects_missing_challenge(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "verify-me")
    response = client.get(
        "/webhooks/instagram",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-me"},
    )
    assert response.status_code == 403


def test_webhook_ignores_empty_text_without_storing(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setattr(
        webhook,
        "store_dm_message",
        lambda *_args, **_kwargs: pytest.fail("Empty message text must not be stored"),
    )
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{
            "sender": {"id": "12345"},
            "message": {"mid": "empty-text-mid", "text": "   "},
        }]}],
    })
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0
    assert response.json()["automatic_replies_sent"] == 0


def _timestamp_payload(timestamp, message_id="window-check-mid"):
    return {
        "entry": [{"messaging": [{
            "sender": {"id": "12345"},
            "timestamp": timestamp,
            "message": {"mid": message_id, "text": "Hello NOVA"},
        }]}],
    }


@pytest.mark.parametrize("event", [
    {"sender": {}, "message": {"text": "Hello"}},
    {"sender": {"id": 12345}, "message": {"text": "Hello"}},
])
def test_webhook_ignores_missing_or_nonstring_sender_id(monkeypatch, event):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: pytest.fail("Invalid sender must not be stored"))
    response = _post_signed_payload(monkeypatch, {"entry": [{"messaging": [event]}]})
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0
    assert response.json()["automatic_replies_sent"] == 0


@pytest.mark.parametrize("message", [
    {"mid": "missing-text-mid"},
    {"mid": "nonstring-text-mid", "text": 123},
])
def test_webhook_ignores_missing_or_nonstring_message_text(monkeypatch, message):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: pytest.fail("Invalid text must not be stored"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{"sender": {"id": "12345"}, "message": message}]}],
    })
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0
    assert response.json()["automatic_replies_sent"] == 0


def test_webhook_without_stable_message_id_never_attempts_auto_reply(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    stored = []
    monkeypatch.setattr(webhook, "store_dm_message", lambda *a, **k: (stored.append((a, k)) or "stored"))
    monkeypatch.setattr(webhook, "claim_dm_event", lambda *_a, **_k: pytest.fail("No stable ID means no retry claim"))
    monkeypatch.setattr(webhook, "generate_dm_reply", lambda *_a, **_k: pytest.fail("No stable ID means no reply"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{
            "sender": {"id": "12345"},
            "timestamp": 1_900_000_000_000,
            "message": {"text": "Hello without MID"},
        }]}],
    })
    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1
    assert len(stored) == 1


def test_webhook_disabled_auto_replies_never_claim_or_generate(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: "stored")
    monkeypatch.setattr(webhook, "claim_dm_event", lambda *_a, **_k: pytest.fail("Disabled replies must not claim"))
    monkeypatch.setattr(webhook, "generate_dm_reply", lambda *_a, **_k: pytest.fail("Disabled replies must not generate"))
    response = _post_signed_payload(monkeypatch, _timestamp_payload(1_900_000_000_000, "disabled-reply-mid"))
    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1


def test_webhook_duplicate_claim_is_skipped_before_storage(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setattr(webhook, "claim_dm_event", lambda *_a, **_k: False)
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: pytest.fail("Duplicate must not be stored again"))
    response = _post_signed_payload(monkeypatch, _timestamp_payload(1_900_000_000_000, "duplicate-mid"))
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1


@pytest.mark.parametrize("timestamp", [1, 10 ** 12 + 10 ** 15, 0, -1])
def test_webhook_ignores_outside_or_invalid_timestamp_window(monkeypatch, timestamp):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    finished = []
    monkeypatch.setattr(webhook, "claim_dm_event", lambda *_a, **_k: True)
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: "stored")
    monkeypatch.setattr(webhook, "finish_dm_event", lambda message_id, status: finished.append((message_id, status)))
    monkeypatch.setattr(webhook, "generate_dm_reply", lambda *_a, **_k: pytest.fail("Ineligible timestamp must not generate a reply"))
    response = _post_signed_payload(monkeypatch, _timestamp_payload(timestamp, f"bad-window-{timestamp}"))
    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1
    assert finished == [(f"bad-window-{timestamp}", "ignored")]


@pytest.mark.parametrize("sender", [
    None, [], "12345", 12345,
])
def test_webhook_ignores_nonobject_sender_without_crashing(monkeypatch, sender):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: pytest.fail("Invalid sender must not be stored"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{"sender": sender, "message": {"text": "Hi"}}]}],
    })
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0


@pytest.mark.parametrize("message", [
    None, [], "hello", 123,
])
def test_webhook_ignores_nonobject_message_without_crashing(monkeypatch, message):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: pytest.fail("Invalid message must not be stored"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{"sender": {"id": "12345"}, "message": message}]}],
    })
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0


@pytest.mark.parametrize("text", ["", " ", "\n\t", None, 0])
def test_webhook_ignores_blank_or_nonstring_text_without_storage(monkeypatch, text):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: pytest.fail("Blank/invalid text must not be stored"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{"sender": {"id": "12345"}, "message": {"text": text}}]}],
    })
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0


@pytest.mark.parametrize("message", [
    {"text": "echo", "is_echo": True},
    {"text": "echo", "is_echo": 1},
])
def test_webhook_skips_echo_messages(monkeypatch, message):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: pytest.fail("Echo must not be stored"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{"sender": {"id": "12345"}, "message": message}]}],
    })
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0


def test_webhook_trims_text_before_storing(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    stored = []
    monkeypatch.setattr(webhook, "store_dm_message", lambda sender, role, text, message_id=None: (stored.append((sender, role, text, message_id)) or "stored"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{"sender": {"id": "12345"}, "message": {"mid": "trim-mid", "text": "  hello NOVA  "}}]}],
    })
    assert response.status_code == 200
    assert stored == [("12345", "user", "hello NOVA", "trim-mid")]
    assert response.json()["stored_text_messages"] == 1


@pytest.mark.parametrize("payload", [
    None, [], "not-an-object", 7,
])
def test_webhook_ignores_nonobject_top_level_payload(monkeypatch, payload):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    raw = __import__("json").dumps(payload).encode()
    import hashlib, hmac
    signature = hmac.new(b"test-app-secret", raw, hashlib.sha256).hexdigest()
    response = client.post("/webhooks/instagram", content=raw, headers={"X-Hub-Signature-256": f"sha256={signature}"})
    assert response.status_code in (200, 400)
    assert response.status_code != 500


@pytest.mark.parametrize("entry", [
    None, [], "bad-entry", 42,
])
def test_webhook_ignores_nonobject_entry_without_crashing(monkeypatch, entry):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    response = _post_signed_payload(monkeypatch, {"entry": [entry]})
    assert response.status_code == 200


@pytest.mark.parametrize("messaging", [
    None, {}, "bad-messaging", 42,
])
def test_webhook_ignores_nonlist_messaging_without_crashing(monkeypatch, messaging):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    response = _post_signed_payload(monkeypatch, {"entry": [{"messaging": messaging}]})
    assert response.status_code == 200


@pytest.mark.parametrize("event", [
    None, "bad-event", 42,
])
def test_webhook_ignores_nonobject_messaging_event(monkeypatch, event):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    response = _post_signed_payload(monkeypatch, {"entry": [{"messaging": [event]}]})
    assert response.status_code == 200


@pytest.mark.parametrize("timestamp", ["not-a-number", {}, [], True])
def test_webhook_ignores_malformed_timestamp_types(monkeypatch, timestamp):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setattr(webhook, "claim_dm_event", lambda *_a, **_k: True)
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: "stored")
    monkeypatch.setattr(webhook, "finish_dm_event", lambda *_a, **_k: None)
    monkeypatch.setattr(webhook, "generate_dm_reply", lambda *_a, **_k: pytest.fail("Malformed timestamp must not trigger reply"))
    response = _post_signed_payload(monkeypatch, _timestamp_payload(timestamp, f"bad-type-{type(timestamp).__name__}"))
    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1


@pytest.mark.parametrize("message_id", [None, "", 123, [], {}])
def test_webhook_ignores_missing_or_invalid_message_id_for_reply_claim(monkeypatch, message_id):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: "stored")
    monkeypatch.setattr(webhook, "claim_dm_event", lambda *_a, **_k: pytest.fail("Invalid message ID must not be claimed"))
    monkeypatch.setattr(webhook, "generate_dm_reply", lambda *_a, **_k: pytest.fail("Invalid message ID must not trigger reply"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{
            "sender": {"id": "12345"},
            "message": {"mid": message_id, "text": "Hello"},
        }]}],
    })
    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0


@pytest.mark.parametrize("timestamp", [None, "", "0", "1700000000000", -0.5, 0.5, 1.5, 2**53, 2**63, 10**30, float("nan"), float("inf"), float("-inf"), [], {}])
def test_webhook_malformed_timestamp_never_replies_and_finishes_ignored(monkeypatch, timestamp):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    finished = []
    monkeypatch.setattr(webhook, "claim_dm_event", lambda *_a, **_k: True)
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: "stored")
    monkeypatch.setattr(webhook, "finish_dm_event", lambda message_id, status: finished.append((message_id, status)))
    monkeypatch.setattr(webhook, "generate_dm_reply", lambda *_a, **_k: pytest.fail("Malformed timestamp must not generate a reply"))
    response = _post_signed_payload(monkeypatch, _timestamp_payload(timestamp, f"next15-{len(str(timestamp))}-{type(timestamp).__name__}"))
    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1
    assert finished and finished[0][1] == "ignored"


@pytest.mark.parametrize("message_id", [False, True, 0, 1.5, "x" * 513, ["nested"], {"nested": "id"}, 10**100, -1, None])
def test_webhook_rejects_noncanonical_message_ids_without_claiming(monkeypatch, message_id):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: "stored")
    monkeypatch.setattr(webhook, "claim_dm_event", lambda *_a, **_k: pytest.fail("Invalid message ID must not be claimed"))
    monkeypatch.setattr(webhook, "generate_dm_reply", lambda *_a, **_k: pytest.fail("Invalid message ID must not trigger reply"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{
            "sender": {"id": "12345"},
            "message": {"mid": message_id, "text": "Hello"},
        }]}],
    })
    assert response.status_code == 200
    assert response.json()["automatic_replies_sent"] == 0


@pytest.mark.parametrize("text", ["\r", "\v", "\f", "\u00a0", "\u2003", "\u2028", "\u2029", "\u3000", "\x1c", "\x1d", "\x1e", "\x85", "\u1680", "\u2000", " \t\n "])
def test_webhook_does_not_store_unicode_or_control_whitespace_only_text(monkeypatch, text):
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")
    monkeypatch.setattr(webhook, "store_dm_message", lambda *_a, **_k: pytest.fail("Whitespace-only text must not be stored"))
    response = _post_signed_payload(monkeypatch, {
        "entry": [{"messaging": [{
            "sender": {"id": "12345"},
            "message": {"mid": "whitespace-next15", "text": text},
        }]}],
    })
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0


def test_webhook_rejects_oversized_payload_before_signature_check(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    payload = b"x" * (webhook.MAX_WEBHOOK_BODY_BYTES + 1)

    response = client.post("/webhooks/instagram", content=payload)

    assert response.status_code == 413
    assert response.json()["detail"] == "Webhook payload exceeds the 1 MiB limit."
