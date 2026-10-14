from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from database import db
from services import order_service as svc
from auth import get_current_user, require_roles, tenant_id_of
from models import (serialize, RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF)

# ---- Public order placement + tracking (client / widget) ----
public_router = APIRouter(prefix="/public/orders", tags=["public-orders"])
# ---- Dashboard order management (authenticated, tenant-scoped) ----
router = APIRouter(prefix="/orders", tags=["orders"])

MANAGE = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER)
OPERATE = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF)


class CustomerInfo(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: Optional[str] = ""
    phone: str = Field(min_length=3)
    email: Optional[str] = ""
    address: Optional[str] = ""


class PlaceOrderBody(BaseModel):
    cart_id: str
    customer: CustomerInfo
    order_type: str
    delivery_zone_id: Optional[str] = None
    customer_note: Optional[str] = ""


class StatusBody(BaseModel):
    status: str


class CancelBody(BaseModel):
    reason: Optional[str] = ""


def _public_order_view(o: dict) -> dict:
    return {
        "reference": o["reference"], "status": o["status"], "order_type": o["order_type"],
        "subtotal": o["subtotal"], "delivery_fee": o["delivery_fee"], "total": o["total"],
        "items": [{"name": it["item_name_snapshot"], "quantity": it["quantity"],
                   "unit_price": it["unit_price_snapshot"], "line_total": it["line_total"],
                   "options": [op["option_name_snapshot"] for op in it.get("options", [])]} for it in o["items"]],
        "delivery_address": o.get("delivery_address", ""), "delivery_zone_name": o.get("delivery_zone_name"),
        "customer_name": f"{o['customer_snapshot'].get('first_name','')} {o['customer_snapshot'].get('last_name','')}".strip(),
        "created_at": o["created_at"], "tracking_token": o.get("tracking_token"),
    }


# ================= PUBLIC =================
@public_router.post("")
async def place_order(body: PlaceOrderBody, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    cart = await svc.get_cart(db, body.cart_id)
    rid = cart["restaurant_id"]
    order = await svc.create_order(
        db, rid, cart, body.customer.model_dump(), body.order_type,
        delivery_zone_id=body.delivery_zone_id, customer_note=body.customer_note or "",
        idempotency_key=idempotency_key, created_by=None)
    return _public_order_view(order)


@public_router.get("/{tracking_token}")
async def track_order(tracking_token: str):
    o = await db.orders.find_one({"tracking_token": tracking_token})
    if not o:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return _public_order_view(serialize(o))


# ================= DASHBOARD =================
@router.get("")
async def list_orders(status: Optional[str] = None, period: Optional[str] = None,
                      user: dict = Depends(OPERATE)):
    rid = tenant_id_of(user)
    q = {"restaurant_id": rid}
    if status and status != "all":
        q["status"] = status
    if period in ("today", "week", "month"):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=7)
        else:
            start = now - timedelta(days=30)
        q["created_at"] = {"$gte": start.isoformat()}
    docs = await db.orders.find(q).sort("created_at", -1).to_list(2000)
    return [serialize(d) for d in docs]


@router.get("/{order_id}")
async def get_order(order_id: str, user: dict = Depends(OPERATE)):
    rid = tenant_id_of(user)
    order = await svc.get_order(db, rid, order_id)
    history = await db.order_status_history.find({"order_id": order_id, "restaurant_id": rid}).sort("created_at", 1).to_list(100)
    order["history"] = [serialize(h) for h in history]
    return order


@router.patch("/{order_id}/status")
async def change_status(order_id: str, body: StatusBody, user: dict = Depends(OPERATE)):
    rid = tenant_id_of(user)
    return await svc.update_order_status(db, rid, order_id, body.status, changed_by=user["_id"])


@router.post("/{order_id}/cancel")
async def cancel(order_id: str, body: CancelBody, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    return await svc.cancel_order(db, rid, order_id, body.reason or "", cancelled_by=user["_id"])
