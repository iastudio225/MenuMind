"""D1.27 — order integrity tests (mocked services, no network, no real DB).

Covers the scenarios identified by the launch audit:
- server-enforced recap sequence (calculate_cart marker + cart fingerprint);
- confirmation out-of-context or after a cart/delivery/fee change is refused;
- fingerprint insensitive to cart line order (G2);
- idempotent create_order retry at conversation level AND at DB level (G3);
- malformed model args map to controlled 400 (never 500);
- a failed create_order never leaves a "success" text as the final message;
- provider/backend failure mid-turn never yields a phantom order.

Limits of this suite (G3 documentation): FakeDB simulates the unique sparse
index (restaurant_id, idempotency_key) of seed.py by raising DuplicateKeyError
on conflicting inserts, and Svc.create_order mirrors the pre-check + duplicate
recovery of order_service.create_order. It does NOT reproduce real MongoDB:
no sessions/transactions, no TTL, no true parallel interleaving (tests are
sequential), and validate_cart is stubbed valid (no price revalidation).
Concurrency guarantees ultimately rest on the real index (exercised by the
integration suite tests/test_orders.py, not run here)."""
import json

import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from services.ai import agent_service as ag
from services.ai import quota
from services.ai import tools as tools_mod
from services.ai.provider import ScriptedProvider


def _run(coro):
    import asyncio
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _fresh_quota():
    quota.reset()
    yield
    quota.reset()


# =============== Fakes (self-contained) ===============
class FakeDB:
    def __init__(self):
        self.ai_conversations = self._Col()
        # G3: emulate the unique sparse index (restaurant_id, idempotency_key)
        # declared in seed.py — a conflicting insert raises DuplicateKeyError
        # exactly like MongoDB would under an insert race.
        self.orders = self._Col(unique=[("restaurant_id", "idempotency_key")])

    class _Col:
        def __init__(self, unique=()):
            self.docs = []
            self.unique = unique  # list of key tuples; sparse (None values not indexed)

        async def find_one(self, q):
            for d in self.docs:
                if all(d.get(k) == v for k, v in q.items()):
                    return d
            return None

        async def insert_one(self, doc):
            for keys in self.unique:
                vals = [doc.get(k) for k in keys]
                if all(v is not None for v in vals):
                    for d in self.docs:
                        if all(d.get(k) == v for k, v in zip(keys, vals)):
                            raise DuplicateKeyError(f"E11000 duplicate key: {keys}")
            doc.setdefault("_id", f"oid-{len(self.docs) + 1}")
            self.docs.append(doc)

        async def update_one(self, q, update):
            doc = await self.find_one(q)
            if doc and "$set" in update:
                doc.update(update["$set"])


class Svc:
    """Order-capable fake mirroring order_service.create_order idempotency:
    pre-check by (restaurant_id, idempotency_key), then insert guarded by the
    unique index (DuplicateKeyError -> return the winner). Does not revalidate
    prices (validate_cart is a stub)."""

    def __init__(self):
        self.cart = {"_id": "cart-doc-1", "cart_id": "cart-1",
                     "restaurant_id": "rest-1", "items": []}
        self.orders_created = []
        self.fail_next_create = None  # exception raised on next create_order
        self.bypass_precheck = False  # G3: simulate a true race (both requests pre-checked before either insert)
        self.fee_by_zone = {"z1": 1000}

    def now_iso(self):
        return "2026-10-09T12:00:00Z"

    async def get_cart(self, db, cart_id, restaurant_id=None):
        c = dict(self.cart)
        c["items"] = [dict(i) for i in self.cart["items"]]
        return c

    async def add_to_cart(self, db, restaurant_id, cart, item_id, quantity, option_ids):
        self.cart["items"].append({"cart_item_id": f"ci-{len(self.cart['items'])+1}",
                                   "item_id": item_id, "quantity": quantity,
                                   "option_ids": option_ids or []})
        return await self.get_cart(db, self.cart["cart_id"])

    async def calculate_cart(self, db, restaurant_id, cart, delivery_fee=0):
        return {"items": cart.get("items", []), "subtotal": 12000,
                "delivery_fee": delivery_fee, "total": 12000 + delivery_fee}

    async def calculate_delivery_fee(self, db, restaurant_id, order_type, zone_id):
        return self.fee_by_zone.get(zone_id, 0)

    async def validate_cart(self, db, restaurant_id, cart):
        return {"valid": True, "issues": []}

    @staticmethod
    def _as_order(doc):
        return {"reference": doc["reference"], "status": doc["status"],
                "total": doc["total"], "tracking_token": doc["tracking_token"]}

    async def create_order(self, db, restaurant_id, cart, customer_data, order_type,
                           delivery_zone_id=None, customer_note="", idempotency_key=None,
                           created_by=None):
        if self.fail_next_create is not None:
            exc = self.fail_next_create
            self.fail_next_create = None
            raise exc
        # Same contract as order_service.create_order:325-328,393-401.
        if idempotency_key and not self.bypass_precheck:
            existing = await db.orders.find_one({"restaurant_id": restaurant_id,
                                                 "idempotency_key": idempotency_key})
            if existing:
                return self._as_order(existing)
        order = {"reference": f"CMD-T{len(self.orders_created)+1}", "status": "PENDING",
                 "total": 12000, "tracking_token": "tok"}
        try:
            await db.orders.insert_one({"restaurant_id": restaurant_id,
                                        "reference": order["reference"],
                                        "idempotency_key": idempotency_key,
                                        "status": order["status"], "total": order["total"],
                                        "tracking_token": order["tracking_token"]})
        except Exception:
            if idempotency_key:
                existing = await db.orders.find_one({"restaurant_id": restaurant_id,
                                                     "idempotency_key": idempotency_key})
                if existing:
                    return self._as_order(existing)
            raise
        self.orders_created.append(order)
        return order


class _AgentSvc:
    """Minimal agent-side surface (process_message only needs these)."""

    def __init__(self, inner):
        self._inner = inner

    def now_iso(self):
        return self._inner.now_iso()

    async def get_restaurant_by_public_id(self, db, public_id):
        if public_id != "rest_demo_chezawa":
            raise HTTPException(status_code=404, detail="Restaurant introuvable")
        return {"_id": "rest-1", "name": "Chez Awa", "public_id": public_id}

    async def create_cart(self, db, restaurant_id, session_id=None):
        return {"cart_id": "cart-1"}

    async def get_available_menu(self, db, restaurant_id):
        return {"categories": []}

    async def get_delivery_zones(self, db, restaurant_id, active_only=False):
        return [{"id": "z1", "name": "Cocody", "fee": 1000}]

    async def get_cart(self, db, cart_id, restaurant_id=None):
        return await self._inner.get_cart(db, cart_id, restaurant_id)

    async def calculate_cart(self, db, restaurant_id, cart, delivery_fee=0):
        return await self._inner.calculate_cart(db, restaurant_id, cart, delivery_fee)


@pytest.fixture
def svc(monkeypatch):
    """Wire the fake service into tools (real execute_tool path)."""
    s = Svc()
    monkeypatch.setattr(tools_mod, "svc", s)
    return s


def _j(message, tool=None, args=None):
    return json.dumps({"message": message, "tool": tool, "args": args or {}},
                      ensure_ascii=False)


def _queue(items):
    it = iter(items)

    def handler(system_prompt, messages):
        try:
            return next(it)
        except StopIteration:
            raise AssertionError("provider queue exhausted")
    return handler


def _conv(**over):
    c = {"_id": "conv-1", "conversation_id": "conv-1", "restaurant_id": "rest-1",
         "cart_id": "cart-1", "draft": {}, "customer": {}, "order_reference": None,
         "messages": []}
    c.update(over)
    return c


def _ready_conv():
    """Delivery draft + customer + valid cart (recap marker set separately)."""
    return _conv(draft={"order_type": "DELIVERY", "delivery_zone_id": "z1",
                        "delivery_fee": 1000, "address": "Rue 12"},
                 customer={"first_name": "Jean", "phone": "0707070707"})


def _prep(db, conv):
    _run(tools_mod.execute_tool(db, conv, "set_fulfillment",
                                {"order_type": "DELIVERY", "delivery_zone_id": "z1",
                                 "address": "Rue 12"}, "livraison"))
    _run(tools_mod.execute_tool(db, conv, "set_customer",
                                {"first_name": "Jean", "phone": "0707070707"}, "infos"))
    _run(tools_mod.execute_tool(db, conv, "calculate_cart", {}, "récap"))


# =============== 1-2. Server-enforced recap sequence ===============
def test_create_order_without_recap_is_refused(svc):
    db = FakeDB()
    conv = _ready_conv()  # affirmation-ready but no calculate_cart marker
    with pytest.raises(HTTPException) as e:
        _run(tools_mod.execute_tool(db, conv, "create_order", {}, "ok"))
    assert e.value.status_code == 400
    assert "Récapitulatif" in e.value.detail
    assert svc.orders_created == []


def test_create_order_refused_when_cart_changed_after_recap(svc):
    db = FakeDB()
    conv = _ready_conv()
    _prep(db, conv)
    # cart mutates after the recap (model adds an item before the "oui")
    _run(tools_mod.execute_tool(db, conv, "add_to_cart",
                                {"item_id": "poulet", "quantity": 2}, "ajoute aussi"))
    with pytest.raises(HTTPException) as e:
        _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert e.value.status_code == 400
    assert "panier modifié" in e.value.detail
    assert svc.orders_created == []


def test_delivery_choice_change_after_recap_also_refused(svc):
    db = FakeDB()
    conv = _ready_conv()
    _prep(db, conv)
    _run(tools_mod.execute_tool(db, conv, "set_fulfillment",
                                {"order_type": "PICKUP"}, "finalement retrait"))
    with pytest.raises(HTTPException) as e:
        _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert e.value.status_code == 400
    assert svc.orders_created == []


# =============== 3. Nominal path + idempotent retry ===============
def test_nominal_recap_then_confirm_then_idempotent_retry(svc):
    db = FakeDB()
    conv = _ready_conv()
    _prep(db, conv)
    result, order = _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert result == {"status": "created"}
    assert order["reference"] == "CMD-T1"
    assert len(svc.orders_created) == 1
    # double submission (same conversation): served from the idempotency store
    result2, order2 = _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert result2["status"] == "already_created"
    assert order2["reference"] == "CMD-T1"
    assert len(svc.orders_created) == 1  # never a second order


# =============== 4. Mid-op backend failure then retry heals ===============
def test_backend_failure_mid_create_then_retry_single_order(svc):
    db = FakeDB()
    conv = _ready_conv()
    _prep(db, conv)
    svc.fail_next_create = RuntimeError("socket dead during insert")
    with pytest.raises(RuntimeError):
        _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert conv.get("order_reference") is None  # not marked as ordered
    _, order = _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert order["reference"] == "CMD-T1"
    assert len(svc.orders_created) == 1
    result3, _ = _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert result3["status"] == "already_created"
    assert len(svc.orders_created) == 1


# =============== 5. Malformed args -> controlled 400 ===============
def test_missing_item_id_maps_to_400(svc):
    db = FakeDB()
    conv = _conv()
    with pytest.raises(HTTPException) as e:
        _run(tools_mod.execute_tool(db, conv, "add_to_cart", {"quantity": 1}, "ajoute"))
    assert e.value.status_code == 400
    assert "invalides" in e.value.detail


def test_non_numeric_quantity_maps_to_400(svc):
    db = FakeDB()
    conv = _conv()
    with pytest.raises(HTTPException) as e:
        _run(tools_mod.execute_tool(db, conv, "add_to_cart",
                                    {"item_id": "poulet", "quantity": "abc"}, "ajoute"))
    assert e.value.status_code == 400
    assert svc.cart["items"] == []


# =============== 6. Failed create_order leaves no success text ===============
def test_failed_create_order_does_not_leave_success_message(monkeypatch, svc):
    db = FakeDB()

    async def boom(*a, **k):
        raise HTTPException(status_code=409, detail="Panier invalide")

    svc.create_order = boom
    monkeypatch.setattr(ag, "svc", _AgentSvc(svc))
    conv = _ready_conv()
    db.ai_conversations.docs.append(conv)
    _prep(db, conv)

    provider = ScriptedProvider(_queue([
        _j("Commande créée !", tool="create_order", args={}),
        _j("Désolé, la commande n'a pas pu aboutir."),
    ]))
    out = _run(ag.process_message(db, "rest_demo_chezawa", "conv-1", "je confirme", provider))
    assert out["order"] is None
    assert out["message"] == "Désolé, la commande n'a pas pu aboutir."


# =============== 7. Provider failure mid-turn: no phantom order ===============
def test_provider_failure_mid_turn_yields_controlled_error(monkeypatch, svc):
    db = FakeDB()
    monkeypatch.setattr(ag, "svc", _AgentSvc(svc))
    conv = _ready_conv()
    db.ai_conversations.docs.append(conv)
    _prep(db, conv)

    calls = {"n": 0}

    def flaky(system_prompt, messages):
        calls["n"] += 1
        if calls["n"] == 1:
            return _j("Ajout.", tool="add_to_cart", args={"item_id": "poulet", "quantity": 1})
        raise HTTPException(status_code=504, detail="timeout")

    with pytest.raises(HTTPException) as e:
        _run(ag.process_message(db, "rest_demo_chezawa", "conv-1", "je confirme",
                                ScriptedProvider(flaky)))
    assert e.value.status_code == 504
    assert svc.orders_created == []  # no order created on a failed turn
    assert conv.get("order_reference") is None


# =============== 8. G1 — fee drift between recap and confirmation ===============
def test_delivery_fee_change_after_recap_refused(svc):
    db = FakeDB()
    conv = _ready_conv()
    _prep(db, conv)  # recap presented with fee 1000
    svc.fee_by_zone["z1"] = 1500  # provider changes the zone fee before the "oui"
    with pytest.raises(HTTPException) as e:
        _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert e.value.status_code == 409
    assert "frais de livraison" in e.value.detail
    assert svc.orders_created == []


# =============== 9. G2 — same lines in a different order ===============
def test_same_cart_lines_in_different_order_still_confirms(svc):
    db = FakeDB()
    conv = _ready_conv()
    _run(tools_mod.execute_tool(db, conv, "set_fulfillment",
                                {"order_type": "DELIVERY", "delivery_zone_id": "z1",
                                 "address": "Rue 12"}, "livraison"))
    _run(tools_mod.execute_tool(db, conv, "set_customer",
                                {"first_name": "Jean", "phone": "0707070707"}, "infos"))
    _run(tools_mod.execute_tool(db, conv, "add_to_cart",
                                {"item_id": "poulet", "quantity": 1}, "ajoute"))
    _run(tools_mod.execute_tool(db, conv, "add_to_cart",
                                {"item_id": "attieke", "quantity": 2}, "ajoute aussi"))
    _run(tools_mod.execute_tool(db, conv, "calculate_cart", {}, "récap"))
    svc.cart["items"].reverse()  # identical content, different line order
    _, order = _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert order["reference"] == "CMD-T1"
    assert len(svc.orders_created) == 1


# =============== 10. G3 — DB-level idempotency ===============
def test_retry_after_lost_conv_reference_served_from_db_idempotency(svc):
    """Order exists in DB but the conversation reference was never written
    (crash between insert and conv update): retry must return the same order
    through the (restaurant_id, idempotency_key) pre-check, not create a new one."""
    db = FakeDB()
    conv = _ready_conv()
    _prep(db, conv)
    _, order1 = _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert order1["reference"] == "CMD-T1"
    conv["order_reference"] = None  # simulate the lost conv update
    _, order2 = _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert order2["reference"] == "CMD-T1"  # winner returned, not a new order
    assert len(db.orders.docs) == 1
    assert len(svc.orders_created) == 1
    assert conv["order_reference"] == "CMD-T1"  # conversation healed


def test_insert_race_on_unique_index_returns_winner(svc):
    """True race: both requests pre-checked before either inserted — only the
    unique index can save us. DuplicateKeyError on insert -> return winner."""
    db = FakeDB()
    conv = _ready_conv()
    _prep(db, conv)
    _, order1 = _run(tools_mod.execute_tool(db, conv, "create_order", {}, "je confirme"))
    assert order1["reference"] == "CMD-T1"
    conv["order_reference"] = None
    svc.bypass_precheck = True  # the loser's find_one ran before the winner's insert
    order2 = _run(svc.create_order(db, "rest-1", {"_id": "cart-doc-1"}, {}, "DELIVERY",
                                   delivery_zone_id="z1", idempotency_key="conv:conv-1:cart-1"))
    assert order2["reference"] == "CMD-T1"
    assert len(db.orders.docs) == 1  # unique index blocked the duplicate
