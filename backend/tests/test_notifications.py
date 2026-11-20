"""P3 — webhooks n8n : config, signature, envoi et audit."""
import hashlib
import hmac
import json

from services import notifications


class FakeResponse:
    status_code = 200


class FakeClient:
    last = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, content=None, headers=None):
        FakeClient.last = {"url": url, "content": content, "headers": headers}
        return FakeResponse()


class FakeAuditLogs:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)


class FakeDB:
    def __init__(self):
        self.audit_logs = FakeAuditLogs()


def test_webhook_url_prefers_tenant(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://global.test/hook")
    restaurant = {"notifications": {"webhook_url": "https://tenant.test/hook"}}
    assert notifications.webhook_url_for(restaurant) == "https://tenant.test/hook"


def test_webhook_url_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://global.test/hook")
    assert notifications.webhook_url_for({}) == "https://global.test/hook"


def test_webhook_url_none(monkeypatch):
    monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
    assert notifications.webhook_url_for({"notifications": {}}) is None


def test_signature_is_hmac_sha256():
    body = b'{"event":"test"}'
    expected = "sha256=" + hmac.new(b"s3cr3t", body, hashlib.sha256).hexdigest()
    assert notifications.signature("s3cr3t", body) == expected


def test_build_event_shape():
    event = notifications.build_event(
        {"_id": "rest-1", "name": "Chez Awa", "public_id": "rest_demo", "secteur": "restaurant"},
        "order.created", {"reference": "CMD-1"},
    )
    assert event["event"] == "order.created"
    assert event["restaurant"] == {
        "id": "rest-1", "name": "Chez Awa", "public_id": "rest_demo", "secteur": "restaurant",
    }
    assert event["data"] == {"reference": "CMD-1"}
    assert event["occurred_at"]


def test_order_event_payload_fields():
    order = {
        "reference": "CMD-1", "status": "PENDING", "order_type": "DELIVERY",
        "total": 5000, "subtotal": 4000, "delivery_fee": 1000,
        "customer_snapshot": {"first_name": "Awa", "phone": "+2250700000000"},
        "items": [{"item_name_snapshot": "Eau", "quantity": 2}],
    }
    payload = notifications.order_event_payload(order)
    assert payload["reference"] == "CMD-1"
    assert payload["customer"]["phone"] == "+2250700000000"
    assert payload["items"][0]["quantity"] == 2


def test_dispatch_without_url_does_not_send(monkeypatch):
    monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
    db = FakeDB()
    result = __import__("asyncio").run(
        notifications.dispatch(db, {"_id": "rest-1"}, "test", {})
    )
    assert result == {"sent": False, "reason": "not_configured"}
    assert db.audit_logs.docs == []


def test_dispatch_posts_signed_event_and_audits(monkeypatch):
    monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(notifications.httpx, "AsyncClient", FakeClient)
    db = FakeDB()
    restaurant = {
        "_id": "rest-1", "name": "Chez Awa", "public_id": "rest_demo",
        "notifications": {"webhook_url": "https://n8n.test/hook", "webhook_secret": "s3cr3t"},
    }
    result = __import__("asyncio").run(
        notifications.dispatch(db, restaurant, "order.created", {"reference": "CMD-1"})
    )
    assert result == {"sent": True, "status": 200}
    assert FakeClient.last["url"] == "https://n8n.test/hook"
    headers = FakeClient.last["headers"]
    assert headers["X-MenuMind-Event"] == "order.created"
    body = FakeClient.last["content"]
    assert headers["X-MenuMind-Signature"] == notifications.signature("s3cr3t", body)
    assert json.loads(body)["data"] == {"reference": "CMD-1"}
    assert db.audit_logs.docs[0]["action"] == "WEBHOOK_DELIVERY"
