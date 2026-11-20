"""Outbound webhooks for n8n orchestration (SMS, email, CRM, agenda).

Events are POSTed as JSON to the tenant's configured n8n webhook URL, or the
global `N8N_WEBHOOK_URL` fallback. Delivery is best-effort: a failure is logged
to `audit_logs` and never raised to the caller.

Security: when a secret is configured (`notifications.webhook_secret` or
`WEBHOOK_SECRET`), the raw body is signed with HMAC-SHA256 and exposed in the
`X-MenuMind-Signature` header (`sha256=<hex>`), so n8n can verify authenticity.
"""
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def webhook_url_for(restaurant: dict) -> Optional[str]:
    """Tenant URL wins; the global env var is only a fallback."""
    notifications = (restaurant or {}).get("notifications") or {}
    url = (notifications.get("webhook_url") or os.environ.get("N8N_WEBHOOK_URL") or "").strip()
    return url or None


def webhook_secret_for(restaurant: dict) -> str:
    notifications = (restaurant or {}).get("notifications") or {}
    return (notifications.get("webhook_secret") or os.environ.get("WEBHOOK_SECRET") or "").strip()


def signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def build_event(restaurant: dict, event: str, data: dict) -> dict:
    return {
        "event": event,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "restaurant": {
            "id": str(restaurant.get("_id") or restaurant.get("id") or ""),
            "name": restaurant.get("name", ""),
            "public_id": restaurant.get("public_id", ""),
            "secteur": restaurant.get("secteur", "restaurant"),
        },
        "data": data,
    }


def order_event_payload(order: dict) -> dict:
    """Public-safe order summary for SMS/email/CRM workflows."""
    return {
        "reference": order.get("reference"),
        "status": order.get("status"),
        "order_type": order.get("order_type"),
        "total": order.get("total"),
        "subtotal": order.get("subtotal"),
        "delivery_fee": order.get("delivery_fee"),
        "customer": order.get("customer_snapshot") or {},
        "items": order.get("items") or [],
        "delivery_address": order.get("delivery_address", ""),
        "pickup_address": order.get("pickup_address", ""),
        "dropoff_address": order.get("dropoff_address", ""),
        "tracking_token": order.get("tracking_token"),
        "created_at": order.get("created_at"),
    }


async def dispatch(db, restaurant: dict, event: str, data: dict) -> dict:
    """POST an event to n8n. Never raises; returns a delivery result."""
    url = webhook_url_for(restaurant)
    if not url:
        return {"sent": False, "reason": "not_configured"}

    body = build_event(restaurant, event, data)
    raw = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-MenuMind-Event": event}
    secret = webhook_secret_for(restaurant)
    if secret:
        headers["X-MenuMind-Signature"] = signature(secret, raw)

    timeout = float(os.environ.get("WEBHOOK_TIMEOUT_SECONDS", "5") or 5)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, content=raw, headers=headers)
        result = {"sent": 200 <= resp.status_code < 300, "status": resp.status_code}
    except Exception as exc:  # network, DNS, timeout...
        logger.warning("Webhook delivery failed event=%s error=%s", event, exc)
        result = {"sent": False, "reason": "network_error"}

    restaurant_id = str(restaurant.get("_id") or restaurant.get("id") or "")
    try:
        await db.audit_logs.insert_one({
            "restaurant_id": restaurant_id, "user_id": None,
            "action": "WEBHOOK_DELIVERY",
            "detail": {"event": event, **result},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass
    return result
