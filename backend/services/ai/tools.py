"""
Controlled tool layer for the AI agent.

The agent may ONLY act through these tools. Every tool is tenant-scoped (restaurant_id
is derived from the conversation, never from the model) and delegates to the validated
Phase C business services. Money values proposed by the model are ignored — the server
always recalculates.
"""
import hashlib
import json
import re
import logging
from fastapi import HTTPException

from services import order_service as svc

logger = logging.getLogger(__name__)

AFFIRM = re.compile(
    r"\b(oui|je\s+confirme|confirme[rz]?|c'?est\s+bon|valide[rz]?|d'?accord|parfait|"
    r"allez[-\s]?y|commande[rz]?|go|ok|okay)\b", re.IGNORECASE)

TOOL_NAMES = [
    "get_available_menu", "get_delivery_zones", "add_to_cart", "update_cart_item",
    "remove_from_cart", "set_fulfillment", "set_customer", "calculate_cart", "create_order",
]


def _cart_fingerprint(cart: dict, draft: dict) -> str:
    """Server-side fingerprint of what a recap covers (D1.27).

    Covers cart lines (item, quantity, options — line order normalized) plus the
    delivery choices that change the presented total/address. create_order
    refuses to run when this no longer matches the last calculate_cart result,
    so an order can never differ from the recap the client actually saw.
    """
    lines = [
        {"item_id": i.get("item_id"), "quantity": i.get("quantity"),
         "option_ids": sorted(i.get("option_ids") or [])}
        for i in (cart or {}).get("items", [])
    ]
    # G2: line order must not change the fingerprint (same content = same recap).
    items = sorted(lines, key=lambda l: (str(l["item_id"]), str(l["quantity"]), tuple(l["option_ids"] or [])))
    payload = {
        "items": items,
        "order_type": (draft or {}).get("order_type"),
        "delivery_zone_id": (draft or {}).get("delivery_zone_id"),
        "delivery_fee": (draft or {}).get("delivery_fee"),
        "address": (draft or {}).get("address", ""),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


async def execute_tool(db, conversation: dict, tool: str, args: dict, last_user_message: str):
    """Returns (result_dict, order_dict_or_none). Raises HTTPException mapped to a tool error string by caller."""
    try:
        return await _dispatch(db, conversation, tool, args or {}, last_user_message)
    except HTTPException:
        raise
    except (KeyError, ValueError, TypeError):
        # D1.27: malformed model args (missing key, non-numeric quantity...)
        # must degrade to a controlled 400, never an opaque 500.
        raise HTTPException(status_code=400, detail="Arguments d'outil invalides") from None


async def _dispatch(db, conversation: dict, tool: str, args: dict, last_user_message: str):
    rid = conversation["restaurant_id"]
    cart = await svc.get_cart(db, conversation["cart_id"], rid)

    if tool == "get_available_menu":
        return await svc.get_available_menu(db, rid), None

    if tool == "get_delivery_zones":
        return {"zones": await svc.get_delivery_zones(db, rid, active_only=True)}, None

    if tool == "add_to_cart":
        await svc.add_to_cart(db, rid, cart, args["item_id"], int(args.get("quantity", 1)), args.get("option_ids", []))
        return await _cart_view(db, rid, conversation), None

    if tool == "update_cart_item":
        await svc.update_cart_item(db, rid, cart, args["cart_item_id"], args.get("quantity"), args.get("option_ids"))
        return await _cart_view(db, rid, conversation), None

    if tool == "remove_from_cart":
        await svc.remove_cart_item(db, cart, args["cart_item_id"])
        return await _cart_view(db, rid, conversation), None

    if tool == "set_fulfillment":
        order_type = args.get("order_type")
        if order_type not in ("DELIVERY", "PICKUP"):
            raise HTTPException(status_code=400, detail="Type invalide (DELIVERY ou PICKUP)")
        draft = {"order_type": order_type, "delivery_zone_id": None, "address": ""}
        if order_type == "DELIVERY":
            draft["delivery_zone_id"] = args.get("delivery_zone_id")
            draft["address"] = args.get("address", "") or conversation.get("draft", {}).get("address", "")
            # Validate zone immediately (raises if unknown/inactive)
            fee = await svc.calculate_delivery_fee(db, rid, "DELIVERY", draft["delivery_zone_id"])
            draft["delivery_fee"] = fee
        else:
            draft["delivery_fee"] = 0
        await db.ai_conversations.update_one({"_id": conversation["_id"]}, {"$set": {"draft": draft}})
        conversation["draft"] = draft
        view = await _cart_view(db, rid, conversation)
        return view, None

    if tool == "set_customer":
        cust = {
            "first_name": args.get("first_name", ""), "last_name": args.get("last_name", ""),
            "phone": args.get("phone", ""), "email": args.get("email", ""),
        }
        # Full record stays in MongoDB for order creation; the model only gets
        # family name + first name + a neutral marker (D1.23 privacy).
        await db.ai_conversations.update_one({"_id": conversation["_id"]}, {"$set": {"customer": cust}})
        conversation["customer"] = cust
        return {"customer": _model_customer_view(cust)}, None

    if tool == "calculate_cart":
        # D1.27: remember exactly what the recap covers; create_order will
        # refuse if the cart or delivery choices change before confirmation.
        fp = _cart_fingerprint(cart, conversation.get("draft", {}) or {})
        conversation["recap_fingerprint"] = fp
        await db.ai_conversations.update_one(
            {"_id": conversation["_id"]},
            {"$set": {"recap_fingerprint": fp, "recap_at": svc.now_iso()}})
        return await _cart_view(db, rid, conversation), None

    if tool == "create_order":
        return await _create_order(db, rid, conversation, cart, last_user_message)

    raise HTTPException(status_code=400, detail=f"Outil inconnu: {tool}")


def _model_customer_view(cust: dict) -> dict:
    """Customer data as seen by the model: names (family first) + neutral marker.

    Phone/email are deliberately excluded from anything sent back to the model
    (D1.23); the persisted record keeps them for order creation.
    """
    view = {}
    if cust.get("last_name"):
        view["last_name"] = cust["last_name"]
    if cust.get("first_name"):
        view["first_name"] = cust["first_name"]
    if cust.get("phone") or cust.get("email"):
        view["contact"] = "enregistré"
    return view


async def _cart_view(db, rid, conversation):
    cart = await svc.get_cart(db, conversation["cart_id"], rid)
    draft = conversation.get("draft", {}) or {}
    fee = draft.get("delivery_fee", 0) if draft.get("order_type") == "DELIVERY" else 0
    view = await svc.calculate_cart(db, rid, cart, delivery_fee=fee)
    view["order_type"] = draft.get("order_type")
    view["delivery_zone_id"] = draft.get("delivery_zone_id")
    view["address"] = draft.get("address", "")
    return view


async def _create_order(db, rid, conversation, cart, last_user_message):
    # Idempotent: if this conversation already produced an order, return it.
    if conversation.get("order_reference"):
        o = await db.orders.find_one({"restaurant_id": rid, "reference": conversation["order_reference"]})
        if o:
            from models import serialize
            return {"status": "already_created"}, _order_summary(serialize(o))

    # HARD GUARD: never create without an explicit affirmative from the client.
    if not AFFIRM.search(last_user_message or ""):
        raise HTTPException(status_code=400, detail="Confirmation explicite du client requise avant de créer la commande.")

    draft = conversation.get("draft", {}) or {}
    # D1.27: the recap sequence is enforced by the server, not only the prompt:
    # calculate_cart must have run and the cart/delivery state must be unchanged
    # since, otherwise the order could differ from the recap shown to the client.
    stored_fp = conversation.get("recap_fingerprint")
    if not stored_fp or stored_fp != _cart_fingerprint(cart, draft):
        raise HTTPException(
            status_code=400,
            detail="Récapitulatif non présenté ou panier modifié : recalculez le panier et présentez le récapitulatif avant de confirmer.")
    customer = conversation.get("customer", {}) or {}
    order_type = draft.get("order_type")
    if order_type not in ("DELIVERY", "PICKUP"):
        raise HTTPException(status_code=400, detail="Veuillez préciser livraison ou retrait avant de confirmer.")
    if not customer.get("first_name") or not customer.get("phone"):
        raise HTTPException(status_code=400, detail="Prénom et téléphone du client requis avant de confirmer.")

    # G1: the fee shown in the recap must still be the fee charged now, else the
    # client would confirm a stale total. Recomputed server-side at creation time.
    if order_type == "DELIVERY":
        current_fee = await svc.calculate_delivery_fee(db, rid, "DELIVERY", draft.get("delivery_zone_id"))
        if current_fee != draft.get("delivery_fee"):
            raise HTTPException(status_code=409, detail="Les frais de livraison ont changé : recalculez le panier et présentez le nouveau récapitulatif avant de confirmer.")

    validation = await svc.validate_cart(db, rid, cart)
    if not validation["valid"]:
        raise HTTPException(status_code=409, detail=validation["issues"][0] if validation["issues"] else "Panier invalide")

    customer_data = {**customer, "address": draft.get("address", "")}
    idem = f"conv:{conversation['conversation_id']}:{cart['cart_id']}"
    order = await svc.create_order(
        db, rid, cart, customer_data, order_type,
        delivery_zone_id=draft.get("delivery_zone_id"), customer_note="",
        idempotency_key=idem, created_by=None)
    await db.ai_conversations.update_one(
        {"_id": conversation["_id"]},
        {"$set": {"order_reference": order["reference"], "order_tracking_token": order.get("tracking_token"),
                  "customer_id": order.get("customer_id"), "state": "ORDER_CREATED"}})
    conversation["order_reference"] = order["reference"]
    return {"status": "created"}, _order_summary(order)


def _order_summary(order: dict) -> dict:
    return {"reference": order["reference"], "status": order["status"], "total": order["total"],
            "tracking_token": order.get("tracking_token")}
