"""
Phase C — Order engine business services.

Deterministic, UI-independent service layer. The server is the single source of
truth for prices, availability, delivery fees and totals. The future AI agent (Phase D)
must call THESE services, never write to MongoDB directly.

All functions take `db` + a trusted `restaurant_id` (derived from auth or the public
restaurant context) and never trust client-supplied money values.
"""
import re
import secrets
from datetime import datetime, timezone
from typing import Optional, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from bson import ObjectId
from pymongo import ReturnDocument
from fastapi import HTTPException

from models import serialize, now_iso

ORDER_STATUSES = ["PENDING", "CONFIRMED", "PREPARING", "READY", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"]
ORDER_TYPES = ["DELIVERY", "PICKUP", "DINE_IN"]

# Allowed status transitions (server-controlled)
TRANSITIONS = {
    "PENDING": ["CONFIRMED", "CANCELLED"],
    "CONFIRMED": ["PREPARING", "CANCELLED"],
    "PREPARING": ["READY", "CANCELLED"],
    "READY": ["OUT_FOR_DELIVERY", "DELIVERED"],
    "OUT_FOR_DELIVERY": ["DELIVERED"],
    "DELIVERED": [],
    "CANCELLED": [],
}
CANCELLABLE = ["PENDING", "CONFIRMED", "PREPARING"]


def _oid(value: str, label: str = "identifiant") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{label} invalide")


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    p = re.sub(r"[\s\-().]", "", phone.strip())
    return p


# ---------------- RESTAURANT CONTEXT ----------------
async def get_restaurant(db, restaurant_id: str) -> dict:
    r = await db.restaurants.find_one({"_id": _oid(restaurant_id, "restaurant")})
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    return r


async def get_restaurant_by_public_id(db, public_id: str) -> dict:
    r = await db.restaurants.find_one({"public_id": public_id, "status": "active"})
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    return r


# ---------------- MENU (for AI/widget) ----------------
async def get_available_menu(db, restaurant_id: str) -> dict:
    """Only active categories/items/options, availability flags included."""
    cats = await db.menu_categories.find({"restaurant_id": restaurant_id, "active": True}).sort("display_order", 1).to_list(500)
    groups = {str(g["_id"]): g for g in await db.menu_option_groups.find({"restaurant_id": restaurant_id, "active": True}).to_list(500)}
    options_by_group = {}
    for o in await db.menu_options.find({"restaurant_id": restaurant_id, "active": True}).sort("display_order", 1).to_list(2000):
        options_by_group.setdefault(o["group_id"], []).append(o)
    out = []
    for c in cats:
        items = await db.menu_items.find({"restaurant_id": restaurant_id, "category_id": str(c["_id"]), "active": True}).sort("display_order", 1).to_list(2000)
        item_list = []
        for it in items:
            opt_groups = []
            for gid in it.get("option_group_ids", []):
                g = groups.get(gid)
                if not g:
                    continue
                opt_groups.append({
                    "id": str(g["_id"]), "name": g["name"], "required": g.get("required", False),
                    "min": g.get("min_selections", 0), "max": g.get("max_selections", 1),
                    "choices": [{"id": str(o["_id"]), "name": o["name"], "price_delta": o.get("price_delta", 0),
                                 "available": o.get("available", True)} for o in options_by_group.get(gid, [])],
                })
            item_list.append({"id": str(it["_id"]), "name": it["name"], "description": it.get("description", ""),
                              "image_url": it.get("image_url") or it.get("image", ""),
                              "price": it.get("price", 0), "available": it.get("available", True), "options": opt_groups})
        out.append({"id": str(c["_id"]), "name": c["name"], "items": item_list})
    return {"restaurant": {"public_id": (await get_restaurant(db, restaurant_id))["public_id"],
                           "name": (await get_restaurant(db, restaurant_id))["name"]}, "categories": out}


# ---------------- DAILY MENU (D1.54) ----------------
# Same keys as restaurants.opening_hours and weekly_menu_router.DAYS
# (test_day_menu asserts the two contracts stay identical).
DAY_KEYS = ["monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"]
# Documented fallback: missing, empty or invalid restaurants.timezone values
# never fall back to the machine's local timezone.
DEFAULT_TIMEZONE = "Africa/Abidjan"


def _local_day(tz_name: Optional[str], now: Optional[datetime] = None) -> str:
    """Day key (monday..sunday) of `now` converted to the restaurant timezone.

    - now=None -> current instant (read as UTC);
    - a naive datetime is interpreted as UTC (tests inject aware instants to
      stay deterministic; no ambient machine timezone is ever used);
    - absent/empty/invalid tz_name -> Africa/Abidjan, silently documented —
      a bad config must never crash a conversation nor shift days randomly.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        tz = ZoneInfo(tz_name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return DAY_KEYS[now.astimezone(tz).weekday()]


async def get_day_menu(db, restaurant_id: str, now: Optional[datetime] = None) -> dict:
    """Restaurant menu for its OWN local day (D1.54).

    Returns {"day": <day key>, "status": ..., "items": [...]} with status:
    - "not_configured": no weekly_menus document for the local day -> items=[]
      (the full catalogue is NEVER substituted);
    - "inactive": the day exists but active=False -> items=[];
    - "active": item_ids resolved against get_available_menu, in the planner's
      order. Deleted or inactive items cannot leak (the catalogue is
      tenant-scoped and already excludes active=False); available:False items
      are KEPT with their real flag — same contract as the public catalogue,
      so the caller can present them as unavailable, never as orderable.
    """
    restaurant = await get_restaurant(db, restaurant_id)
    day = _local_day(restaurant.get("timezone") or DEFAULT_TIMEZONE, now)
    doc = await db.weekly_menus.find_one({"restaurant_id": restaurant_id, "day": day})
    if not doc:
        return {"day": day, "status": "not_configured", "items": []}
    if not doc.get("active", True):
        return {"day": day, "status": "inactive", "items": []}
    catalogue = await get_available_menu(db, restaurant_id)
    by_id = {it["id"]: it for cat in catalogue["categories"] for it in cat["items"]}
    items = [by_id[iid] for iid in doc.get("item_ids", []) if iid in by_id]
    return {"day": day, "status": "active", "items": items}


# ---------------- CART ----------------
def _require_open_cart(cart: dict) -> None:
    """D1.50: an ordered/locked cart is immutable.

    Refuses every mutation (add/update/remove/clear), the validation and any
    new order attempt with a 409. Public cart routes AND the AI tools share
    these services, so one guard covers both paths. create_order calls the
    idempotency pre-check BEFORE this guard: a legitimate retry of an
    already-processed request still returns the existing order instead of a
    409. Carts are always created with status="open" (see create_cart)."""
    if cart.get("status") != "open":
        raise HTTPException(status_code=409,
                            detail="Ce panier n'est plus utilisable (commande déjà passée ou fermée).")


async def create_cart(db, restaurant_id: str, session_id: Optional[str] = None) -> dict:
    ts = now_iso()
    doc = {"cart_id": secrets.token_urlsafe(24), "restaurant_id": restaurant_id, "session_id": session_id,
           "customer_id": None, "items": [], "status": "open", "created_at": ts, "updated_at": ts}
    await db.carts.insert_one(doc)
    return doc


async def get_cart(db, cart_id: str, restaurant_id: Optional[str] = None) -> dict:
    q = {"cart_id": cart_id}
    cart = await db.carts.find_one(q)
    if not cart:
        raise HTTPException(status_code=404, detail="Panier introuvable")
    if restaurant_id and cart["restaurant_id"] != restaurant_id:
        raise HTTPException(status_code=404, detail="Panier introuvable")
    return cart


async def _resolve_item(db, restaurant_id: str, item_id: str) -> dict:
    item = await db.menu_items.find_one({"_id": _oid(item_id, "article"), "restaurant_id": restaurant_id})
    if not item:
        raise HTTPException(status_code=400, detail="Article introuvable pour ce restaurant")
    return item


async def _validate_options_for_item(db, restaurant_id: str, item: dict, option_ids: List[str]) -> List[dict]:
    """Returns the option docs. Ensures each option belongs to a group attached to the item."""
    attached_groups = set(item.get("option_group_ids", []))
    resolved = []
    for oid in option_ids:
        opt = await db.menu_options.find_one({"_id": _oid(oid, "option"), "restaurant_id": restaurant_id})
        if not opt:
            raise HTTPException(status_code=400, detail="Option introuvable pour ce restaurant")
        if opt["group_id"] not in attached_groups:
            raise HTTPException(status_code=400, detail=f"L'option « {opt['name']} » n'est pas compatible avec cet article")
        resolved.append(opt)
    return resolved


async def add_to_cart(db, restaurant_id: str, cart: dict, item_id: str, quantity: int, option_ids: List[str]) -> dict:
    _require_open_cart(cart)
    if quantity < 1:
        raise HTTPException(status_code=400, detail="Quantité invalide")
    item = await _resolve_item(db, restaurant_id, item_id)
    options = await _validate_options_for_item(db, restaurant_id, item, option_ids or [])
    cart_item = {
        "cart_item_id": secrets.token_hex(5),
        "item_id": item_id,
        "quantity": int(quantity),
        "option_ids": option_ids or [],
        # Snapshot expected prices at add-time for change detection on validate
        "expected_unit_price": item.get("price", 0),
        "expected_options_total": sum(o.get("price_delta", 0) for o in options),
    }
    await db.carts.update_one({"_id": cart["_id"]},
                              {"$push": {"items": cart_item}, "$set": {"updated_at": now_iso()}})
    return await get_cart(db, cart["cart_id"])


async def update_cart_item(db, restaurant_id: str, cart: dict, cart_item_id: str,
                           quantity: Optional[int], option_ids: Optional[List[str]]) -> dict:
    _require_open_cart(cart)
    line = next((i for i in cart.get("items", []) if i["cart_item_id"] == cart_item_id), None)
    if not line:
        raise HTTPException(status_code=404, detail="Ligne de panier introuvable")
    if quantity is not None:
        if quantity < 1:
            raise HTTPException(status_code=400, detail="Quantité invalide")
        line["quantity"] = int(quantity)
    if option_ids is not None:
        item = await _resolve_item(db, restaurant_id, line["item_id"])
        options = await _validate_options_for_item(db, restaurant_id, item, option_ids)
        line["option_ids"] = option_ids
        line["expected_options_total"] = sum(o.get("price_delta", 0) for o in options)
    await db.carts.update_one({"_id": cart["_id"]},
                              {"$set": {"items": cart["items"], "updated_at": now_iso()}})
    return await get_cart(db, cart["cart_id"])


async def remove_cart_item(db, cart: dict, cart_item_id: str) -> dict:
    _require_open_cart(cart)
    await db.carts.update_one({"_id": cart["_id"]},
                              {"$pull": {"items": {"cart_item_id": cart_item_id}}, "$set": {"updated_at": now_iso()}})
    return await get_cart(db, cart["cart_id"])


async def clear_cart(db, cart: dict) -> dict:
    _require_open_cart(cart)
    await db.carts.update_one({"_id": cart["_id"]}, {"$set": {"items": [], "updated_at": now_iso()}})
    return await get_cart(db, cart["cart_id"])


async def calculate_cart(db, restaurant_id: str, cart: dict,
                         delivery_fee: int = 0, discount: int = 0) -> dict:
    """Authoritative server-side recomputation using CURRENT menu prices."""
    lines = []
    subtotal = 0
    for ci in cart.get("items", []):
        item = await db.menu_items.find_one({"_id": _oid(ci["item_id"]), "restaurant_id": restaurant_id})
        if not item:
            continue
        unit_price = item.get("price", 0)
        opts = []
        opt_total = 0
        for oid in ci.get("option_ids", []):
            opt = await db.menu_options.find_one({"_id": _oid(oid), "restaurant_id": restaurant_id})
            if not opt:
                continue
            opts.append({"option_id": oid, "name": opt["name"], "price_delta": opt.get("price_delta", 0),
                         "available": opt.get("available", True)})
            opt_total += opt.get("price_delta", 0)
        line_total = (unit_price + opt_total) * ci["quantity"]
        subtotal += line_total
        lines.append({
            "cart_item_id": ci["cart_item_id"], "item_id": ci["item_id"], "name": item["name"],
            "quantity": ci["quantity"], "unit_price": unit_price, "options": opts,
            "line_total": line_total, "available": item.get("available", True) and item.get("active", True),
        })
    total = subtotal + int(delivery_fee) - int(discount)
    return {"items": lines, "subtotal": subtotal, "delivery_fee": int(delivery_fee),
            "discount": int(discount), "total": max(total, 0)}


async def validate_cart(db, restaurant_id: str, cart: dict) -> dict:
    """Checks availability, activity, option compatibility, quantities and price changes."""
    _require_open_cart(cart)
    issues = []
    if not cart.get("items"):
        issues.append("Le panier est vide.")
    for ci in cart.get("items", []):
        item = await db.menu_items.find_one({"_id": _oid(ci["item_id"]), "restaurant_id": restaurant_id})
        if not item or not item.get("active", False):
            issues.append("Un article de votre panier n'existe plus.")
            continue
        if not item.get("available", True):
            issues.append(f"« {item['name']} » n'est plus disponible.")
        if ci["quantity"] < 1:
            issues.append(f"Quantité invalide pour « {item['name']} ».")
        if item.get("price", 0) != ci.get("expected_unit_price", item.get("price", 0)):
            issues.append(f"Le prix de « {item['name']} » a changé. Veuillez vérifier votre panier.")
        # Options
        current_opt_total = 0
        attached = set(item.get("option_group_ids", []))
        selected_by_group = {}
        for oid in ci.get("option_ids", []):
            opt = await db.menu_options.find_one({"_id": _oid(oid), "restaurant_id": restaurant_id})
            if not opt or not opt.get("active", False):
                issues.append("Une option de votre panier n'existe plus.")
                continue
            if opt["group_id"] not in attached:
                issues.append(f"L'option « {opt['name']} » n'est pas compatible avec « {item['name']} ».")
            if not opt.get("available", True):
                issues.append(f"L'option « {opt['name']} » n'est plus disponible.")
            current_opt_total += opt.get("price_delta", 0)
            selected_by_group.setdefault(opt["group_id"], 0)
            selected_by_group[opt["group_id"]] += 1
        if current_opt_total != ci.get("expected_options_total", current_opt_total):
            issues.append(f"Le prix des options de « {item['name']} » a changé. Veuillez vérifier votre panier.")
        # Required / min / max per attached group
        for gid in attached:
            g = await db.menu_option_groups.find_one({"_id": _oid(gid), "restaurant_id": restaurant_id, "active": True})
            if not g:
                continue
            count = selected_by_group.get(gid, 0)
            if g.get("required", False) and count < max(1, g.get("min_selections", 1)):
                issues.append(f"Veuillez choisir une option « {g['name']} » pour « {item['name']} ».")
            elif count < g.get("min_selections", 0):
                issues.append(f"Veuillez choisir au moins {g['min_selections']} option(s) « {g['name']} » pour « {item['name']} ».")
            if count > g.get("max_selections", 1):
                issues.append(f"Trop d'options « {g['name']} » pour « {item['name']} » (max {g['max_selections']}).")
    view = await calculate_cart(db, restaurant_id, cart)
    return {"valid": len(issues) == 0, "issues": issues, **view}


# ---------------- DELIVERY ----------------
async def get_delivery_zones(db, restaurant_id: str, active_only: bool = False) -> List[dict]:
    q = {"restaurant_id": restaurant_id}
    if active_only:
        q["active"] = True
    docs = await db.delivery_zones.find(q).sort("fee", 1).to_list(500)
    return [serialize(d) for d in docs]


async def calculate_delivery_fee(db, restaurant_id: str, order_type: str, zone_id: Optional[str]) -> int:
    if order_type != "DELIVERY":
        return 0
    if not zone_id:
        raise HTTPException(status_code=400, detail="Veuillez indiquer votre zone de livraison.")
    zone = await db.delivery_zones.find_one({"_id": _oid(zone_id, "zone"), "restaurant_id": restaurant_id, "active": True})
    if not zone:
        raise HTTPException(status_code=400, detail="Cette zone de livraison n'est pas encore desservie.")
    return int(zone.get("fee", 0))


# ---------------- CUSTOMER ----------------
async def upsert_customer(db, restaurant_id: str, data: dict) -> dict:
    phone = normalize_phone(data.get("phone", ""))
    if not phone:
        raise HTTPException(status_code=400, detail="Le téléphone du client est requis")
    ts = now_iso()
    existing = await db.customers.find_one({"restaurant_id": restaurant_id, "phone": phone})
    fields = {k: data.get(k) for k in ["first_name", "last_name", "email", "address", "notes"] if data.get(k)}
    if existing:
        if fields:
            await db.customers.update_one({"_id": existing["_id"]}, {"$set": {**fields, "updated_at": ts}})
        return await db.customers.find_one({"_id": existing["_id"]})
    doc = {"restaurant_id": restaurant_id, "phone": phone,
           "first_name": data.get("first_name", ""), "last_name": data.get("last_name", ""),
           "email": data.get("email", ""), "address": data.get("address", ""),
           "notes": data.get("notes", ""), "created_at": ts, "updated_at": ts}
    res = await db.customers.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


# ---------------- ORDER ----------------
async def next_reference(db, restaurant_id: str) -> str:
    year = datetime.now(timezone.utc).year
    key = f"{restaurant_id}:{year}"
    doc = await db.counters.find_one_and_update(
        {"_id": key}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return f"CMD-{year}-{doc['seq']:05d}"


async def create_order(db, restaurant_id: str, cart: dict, customer_data: dict,
                       order_type: str, delivery_zone_id: Optional[str] = None,
                       customer_note: str = "", idempotency_key: Optional[str] = None,
                       created_by: Optional[str] = None) -> dict:
    if order_type not in ORDER_TYPES:
        raise HTTPException(status_code=400, detail="Type de commande invalide")

    # Idempotency: same key => return existing order.
    # Runs BEFORE the open-cart guard (D1.50): a legitimate retry of an
    # already-processed request must still return the existing order even
    # though the cart is now "ordered" — not a 409.
    if idempotency_key:
        existing = await db.orders.find_one({"restaurant_id": restaurant_id, "idempotency_key": idempotency_key})
        if existing:
            return serialize(existing)
    _require_open_cart(cart)

    restaurant = await get_restaurant(db, restaurant_id)

    # Revalidate at order time (prices/availability may have changed since cart build)
    validation = await validate_cart(db, restaurant_id, cart)
    if not validation["valid"]:
        raise HTTPException(status_code=409, detail=validation["issues"][0] if validation["issues"] else "Panier invalide")

    delivery_address = customer_data.get("address", "") if order_type == "DELIVERY" else ""
    if order_type == "DELIVERY" and not delivery_address:
        raise HTTPException(status_code=400, detail="L'adresse de livraison est requise")

    delivery_fee = await calculate_delivery_fee(db, restaurant_id, order_type, delivery_zone_id)
    customer = await upsert_customer(db, restaurant_id, customer_data)

    # Build snapshot order items from CURRENT menu
    order_items = []
    subtotal = 0
    for ci in cart.get("items", []):
        item = await db.menu_items.find_one({"_id": _oid(ci["item_id"]), "restaurant_id": restaurant_id})
        if not item:
            continue
        unit_price = item.get("price", 0)
        opt_snaps = []
        opt_total = 0
        for oid in ci.get("option_ids", []):
            opt = await db.menu_options.find_one({"_id": _oid(oid), "restaurant_id": restaurant_id})
            if not opt:
                continue
            opt_snaps.append({"option_id": oid, "option_name_snapshot": opt["name"],
                              "price_delta_snapshot": opt.get("price_delta", 0)})
            opt_total += opt.get("price_delta", 0)
        line_total = (unit_price + opt_total) * ci["quantity"]
        subtotal += line_total
        order_items.append({
            "item_id": ci["item_id"], "item_name_snapshot": item["name"],
            "unit_price_snapshot": unit_price, "quantity": ci["quantity"],
            "options": opt_snaps, "line_total": line_total,
        })

    total = subtotal + delivery_fee
    ts = now_iso()
    zone = None
    if delivery_zone_id and order_type == "DELIVERY":
        zdoc = await db.delivery_zones.find_one({"_id": _oid(delivery_zone_id), "restaurant_id": restaurant_id})
        zone = zdoc["name"] if zdoc else None

    reference = await next_reference(db, restaurant_id)
    order_doc = {
        "reference": reference, "restaurant_id": restaurant_id,
        "restaurant_name_snapshot": restaurant["name"],
        "customer_id": str(customer["_id"]),
        "customer_snapshot": {
            "first_name": customer.get("first_name", ""), "last_name": customer.get("last_name", ""),
            "phone": customer.get("phone", ""), "email": customer.get("email", ""),
        },
        "items": order_items, "subtotal": subtotal, "delivery_fee": delivery_fee,
        "discount": 0, "total": total, "status": "PENDING", "payment_status": "UNPAID",
        "order_type": order_type, "delivery_zone_id": delivery_zone_id, "delivery_zone_name": zone,
        "delivery_address": delivery_address, "customer_note": customer_note or "",
        "tracking_token": secrets.token_urlsafe(16),
        "idempotency_key": idempotency_key, "created_by": created_by,
        "created_at": ts, "updated_at": ts,
    }
    try:
        res = await db.orders.insert_one(order_doc)
    except Exception:
        # Likely duplicate idempotency key under race — return the winner
        if idempotency_key:
            existing = await db.orders.find_one({"restaurant_id": restaurant_id, "idempotency_key": idempotency_key})
            if existing:
                return serialize(existing)
        raise
    order_doc["_id"] = res.inserted_id

    await db.order_status_history.insert_one({"order_id": str(res.inserted_id), "restaurant_id": restaurant_id,
                                              "old_status": None, "new_status": "PENDING",
                                              "changed_by": created_by, "created_at": ts})
    await db.carts.update_one({"_id": cart["_id"]}, {"$set": {"status": "ordered", "customer_id": str(customer["_id"]), "updated_at": ts}})
    await db.audit_logs.insert_one({"restaurant_id": restaurant_id, "user_id": created_by,
                                    "action": "ORDER_CREATE", "detail": reference, "created_at": ts})
    return serialize(order_doc)


async def get_order(db, restaurant_id: str, order_id: str) -> dict:
    o = await db.orders.find_one({"_id": _oid(order_id, "commande"), "restaurant_id": restaurant_id})
    if not o:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return serialize(o)


async def update_order_status(db, restaurant_id: str, order_id: str, new_status: str, changed_by: Optional[str]) -> dict:
    if new_status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Statut invalide")
    o = await db.orders.find_one({"_id": _oid(order_id, "commande"), "restaurant_id": restaurant_id})
    if not o:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    old = o["status"]
    if new_status == old:
        return serialize(o)
    allowed = TRANSITIONS.get(old, [])
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Transition {old} → {new_status} non autorisée")
    if new_status == "OUT_FOR_DELIVERY" and o.get("order_type") != "DELIVERY":
        raise HTTPException(status_code=400, detail="Statut réservé aux commandes en livraison")
    ts = now_iso()
    await db.orders.update_one({"_id": o["_id"]}, {"$set": {"status": new_status, "updated_at": ts}})
    await db.order_status_history.insert_one({"order_id": order_id, "restaurant_id": restaurant_id,
                                              "old_status": old, "new_status": new_status,
                                              "changed_by": changed_by, "created_at": ts})
    await db.audit_logs.insert_one({"restaurant_id": restaurant_id, "user_id": changed_by,
                                    "action": "ORDER_STATUS", "detail": f"{o['reference']}:{old}->{new_status}", "created_at": ts})
    return await get_order(db, restaurant_id, order_id)


async def cancel_order(db, restaurant_id: str, order_id: str, reason: str, cancelled_by: Optional[str]) -> dict:
    o = await db.orders.find_one({"_id": _oid(order_id, "commande"), "restaurant_id": restaurant_id})
    if not o:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    if o["status"] not in CANCELLABLE:
        raise HTTPException(status_code=400, detail=f"Une commande « {o['status']} » ne peut pas être annulée")
    ts = now_iso()
    await db.orders.update_one({"_id": o["_id"]}, {"$set": {
        "status": "CANCELLED", "cancel_reason": reason or "", "cancelled_at": ts,
        "cancelled_by": cancelled_by, "updated_at": ts}})
    await db.order_status_history.insert_one({"order_id": order_id, "restaurant_id": restaurant_id,
                                              "old_status": o["status"], "new_status": "CANCELLED",
                                              "changed_by": cancelled_by, "created_at": ts})
    await db.audit_logs.insert_one({"restaurant_id": restaurant_id, "user_id": cancelled_by,
                                    "action": "ORDER_CANCEL", "detail": o["reference"], "created_at": ts})
    return await get_order(db, restaurant_id, order_id)
