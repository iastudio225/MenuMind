from fastapi import APIRouter, Depends, Query
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from database import db
from auth import get_current_user, tenant_id_of

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Seuil d'alerte "stock bas" (e-commerce). Null = illimité, 0 = rupture.
STOCK_ALERT_THRESHOLD = 5

# Statuts considérés comme "mission active" (logistique).
ACTIVE_MISSION_STATUSES = ["PENDING", "CONFIRMED", "PREPARING", "READY", "OUT_FOR_DELIVERY"]


def _stock_value(stock):
    """Retourne (valeur, statut) ; statut = out | low | None (ou illimité)."""
    if stock is None:
        return None, None
    try:
        value = int(stock)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return value, "out"
    if value <= STOCK_ALERT_THRESHOLD:
        return value, "low"
    return value, None


@router.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    rid = tenant_id_of(user)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=7)).isoformat()

    return await db.dashboard_overview(rid, today, week_start)


@router.get("/sources")
async def traffic_sources(days: int = Query(30, ge=1, le=365),
                          user: dict = Depends(get_current_user)):
    """Link attribution: visits vs orders per source (whatsapp, qr, ...)."""
    rid = tenant_id_of(user)
    sources = await db.dashboard_traffic_sources(rid, days)
    return {"days": days, "sources": sources}


@router.get("/stock-alerts")
async def stock_alerts(user: dict = Depends(get_current_user)):
    """Alertes stock e-commerce : articles, options et variantes sous le seuil."""
    rid = tenant_id_of(user)
    items = await db.menu_items.find({"restaurant_id": rid, "active": True}).to_list(5000)
    options = await db.menu_options.find({"restaurant_id": rid, "active": True}).to_list(5000)
    variants = await db.menu_variants.find({"restaurant_id": rid}).to_list(5000)
    item_by_id = {str(it["_id"]): it for it in items}

    alerts = []

    def add(kind, entity_id, name, sku, stock, extra=None):
        value, status = _stock_value(stock)
        if status is None:
            return
        alert = {"kind": kind, "id": str(entity_id), "name": name or "Sans nom",
                 "sku": sku or "", "stock": value, "status": status}
        if extra:
            alert.update(extra)
        alerts.append(alert)

    for it in items:
        add("item", it["_id"], it.get("name"), it.get("sku"), it.get("stock"))
    for opt in options:
        add("option", opt["_id"], opt.get("name"), "", opt.get("stock"))
    for var in variants:
        if var.get("active") is False:
            continue
        parent = item_by_id.get(var.get("item_id"), {})
        add("variant", var["_id"], parent.get("name"), var.get("sku"), var.get("stock"),
            {"variant_key": var.get("variant_key", ""), "item_id": var.get("item_id")})

    alerts.sort(key=lambda a: (0 if a["status"] == "out" else 1, a["stock"]))
    return {
        "threshold": STOCK_ALERT_THRESHOLD,
        "summary": {
            "out": sum(1 for a in alerts if a["status"] == "out"),
            "low": sum(1 for a in alerts if a["status"] == "low"),
            "total": len(alerts),
        },
        "alerts": alerts[:100],
    }


@router.get("/missions")
async def missions(user: dict = Depends(get_current_user)):
    """Missions logistiques actives (trajet ramassage → livraison)."""
    rid = tenant_id_of(user)
    docs = await db.orders.find({
        "restaurant_id": rid,
        "status": {"$in": ACTIVE_MISSION_STATUSES},
    }).sort("created_at", 1).to_list(50)

    out = []
    for o in docs:
        customer = o.get("customer_snapshot") or {}
        out.append({
            "id": str(o["_id"]),
            "reference": o.get("reference"),
            "status": o.get("status"),
            "order_type": o.get("order_type"),
            "customer_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            "customer_phone": customer.get("phone", ""),
            "pickup_address": o.get("pickup_address", ""),
            "dropoff_address": o.get("dropoff_address", "") or o.get("delivery_address", ""),
            "total": o.get("total", 0),
            "created_at": o.get("created_at"),
            "items": [{"name": it.get("item_name_snapshot"), "quantity": it.get("quantity")}
                      for it in o.get("items", [])],
        })
    return {"missions": out, "total": len(out)}
