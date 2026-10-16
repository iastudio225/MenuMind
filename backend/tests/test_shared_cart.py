"""
MenuMind D1.50 — Shared cart between the AI conversation and the visual menu
(mocked services, no network, no real DB).

Covers the linking contract added to POST /api/public/ai/chat (optional
cart_id in ChatBody -> process_message):
- no cart_id  -> strict historical behavior (conversation-owned cart);
- valid cart  -> the conversation REUSES the visual cart (no second cart);
- foreign/unknown cart -> 404 (existence never disclosed across tenants);
- ordered cart -> 409;
- re-association rules on an EXISTING conversation (same cart / safe switch
  / dangerous switch refused / conversation with an order refused);
- an AI tool mutates the LINKED shared cart (visible to the visual menu);
- the public catalogue now carries image_url (new field, legacy fallback).

The fakes mirror the REAL order_service semantics: get_cart(db, cart_id,
restaurant_id) 404s on unknown OR foreign carts, carts carry a status field,
create_cart is only reached when no cart_id is provided. The image_url tests
exercise the REAL order_service.get_available_menu against in-memory
collections (MenuDB), because that function is the catalogue source of truth.
"""
import json

import pytest
from bson import ObjectId
from fastapi import HTTPException

from services import order_service as real_svc
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


# =============== Fakes ===============
class FakeDB:
    def __init__(self):
        self.ai_conversations = self._ConvCol()

    class _ConvCol:
        def __init__(self):
            self.docs = []

        async def find_one(self, q):
            for d in self.docs:
                if all(d.get(k) == v for k, v in q.items()):
                    return d
            return None

        async def insert_one(self, doc):
            doc.setdefault("_id", f"oid-{len(self.docs) + 1}")
            self.docs.append(doc)

        async def update_one(self, q, update):
            doc = await self.find_one(q)
            if doc and "$set" in update:
                doc.update(update["$set"])


class SharedCartSvc:
    """Stateful multi-cart fake mirroring the real cart contract (D1.50)."""

    def __init__(self):
        self.carts = {
            # open + empty: the visual cart a fresh client would create
            "cart-shared": {"_id": "cd-1", "cart_id": "cart-shared",
                            "restaurant_id": "rest-1", "status": "open", "items": []},
            # second open + empty cart of the SAME restaurant (safe re-link target)
            "cart-empty-b": {"_id": "cd-2", "cart_id": "cart-empty-b",
                             "restaurant_id": "rest-1", "status": "open", "items": []},
            # open + NON-empty: articles at stake, re-link must be refused
            "cart-nonempty": {"_id": "cd-3", "cart_id": "cart-nonempty",
                              "restaurant_id": "rest-1", "status": "open", "items": [
                                  {"cart_item_id": "ci-1", "item_id": "eau", "quantity": 1,
                                   "option_ids": [], "expected_unit_price": 500,
                                   "expected_options_total": 0}]},
            # ordered through the visual checkout: conversation must not ride it
            "cart-ordered": {"_id": "cd-4", "cart_id": "cart-ordered",
                             "restaurant_id": "rest-1", "status": "ordered", "items": [
                                 {"cart_item_id": "ci-9", "item_id": "eau", "quantity": 2,
                                  "option_ids": [], "expected_unit_price": 500,
                                  "expected_options_total": 0}]},
            # open cart of ANOTHER restaurant: 404, never disclosed
            "cart-foreign": {"_id": "cd-5", "cart_id": "cart-foreign",
                             "restaurant_id": "rest-9", "status": "open", "items": []},
        }
        self.created_carts = []  # cart_ids produced by create_cart (historical path)

    def now_iso(self):
        return "2026-10-16T12:00:00Z"

    async def get_restaurant_by_public_id(self, db, public_id):
        if public_id != "rest_demo_chezawa":
            raise HTTPException(status_code=404, detail="Restaurant introuvable")
        return {"_id": "rest-1", "name": "Chez Awa", "public_id": public_id}

    async def get_cart(self, db, cart_id, restaurant_id=None):
        # mirrors order_service.get_cart: unknown OR foreign -> same 404 message
        c = self.carts.get(cart_id)
        if not c or (restaurant_id and c["restaurant_id"] != restaurant_id):
            raise HTTPException(status_code=404, detail="Panier introuvable")
        return {"_id": c["_id"], "cart_id": c["cart_id"], "restaurant_id": c["restaurant_id"],
                "status": c["status"], "items": [dict(i) for i in c["items"]]}

    async def create_cart(self, db, restaurant_id, session_id=None):
        cid = f"cart-auto-{len(self.created_carts) + 1}"
        doc = {"_id": f"cd-auto-{len(self.created_carts) + 1}", "cart_id": cid,
               "restaurant_id": restaurant_id, "status": "open", "items": []}
        self.carts[cid] = doc
        self.created_carts.append(cid)
        return dict(doc)

    async def get_available_menu(self, db, restaurant_id):
        return {"restaurant": {"public_id": "rest_demo_chezawa", "name": "Chez Awa"},
                "categories": [{"id": "c1", "name": "Boissons", "items": [
                    {"id": "eau", "name": "Eau minérale", "price": 500, "available": True,
                     "options": []}]}]}

    async def get_delivery_zones(self, db, restaurant_id, active_only=False):
        return [{"id": "z1", "name": "Cocody", "fee": 1000}]

    async def add_to_cart(self, db, restaurant_id, cart, item_id, quantity, option_ids):
        live = self.carts[cart["cart_id"]]
        live["items"].append({"cart_item_id": f"ci-{len(live['items']) + 1}",
                              "item_id": item_id, "quantity": int(quantity),
                              "option_ids": list(option_ids or []),
                              "expected_unit_price": 500, "expected_options_total": 0})
        return await self.get_cart(db, cart["cart_id"])

    async def update_cart_item(self, db, restaurant_id, cart, cart_item_id,
                               quantity=None, option_ids=None):
        live = self.carts[cart["cart_id"]]
        line = next((i for i in live["items"] if i["cart_item_id"] == cart_item_id), None)
        if not line:
            raise HTTPException(status_code=404, detail="Ligne de panier introuvable")
        if quantity is not None:
            line["quantity"] = int(quantity)
        if option_ids is not None:
            line["option_ids"] = list(option_ids)
        return await self.get_cart(db, cart["cart_id"])

    async def remove_cart_item(self, db, cart, cart_item_id):
        live = self.carts[cart["cart_id"]]
        live["items"] = [i for i in live["items"] if i["cart_item_id"] != cart_item_id]
        return await self.get_cart(db, cart["cart_id"])

    async def calculate_cart(self, db, restaurant_id, cart, delivery_fee=0, discount=0):
        lines, subtotal = [], 0
        for ci in cart.get("items", []):
            unit = 500
            line_total = unit * int(ci["quantity"])
            subtotal += line_total
            lines.append({"cart_item_id": ci["cart_item_id"], "item_id": ci["item_id"],
                          "name": ci["item_id"], "quantity": ci["quantity"],
                          "unit_price": unit, "options": ci.get("option_ids", []),
                          "line_total": line_total, "available": True})
        return {"items": lines, "subtotal": subtotal, "delivery_fee": int(delivery_fee),
                "discount": 0, "total": max(subtotal + int(delivery_fee), 0)}


class AgentHarness:
    def __init__(self, replies, fake_svc):
        self.svc = fake_svc
        self.db = FakeDB()
        self.prompts = []
        self.turns = []
        self.provider_calls = 0
        self.queue = list(replies)

        def handler(system_prompt, messages):
            self.provider_calls += 1
            self.prompts.append(system_prompt)
            self.turns.append(messages)
            if not self.queue:
                raise AssertionError(f"model called {self.provider_calls} times, queue empty")
            return self.queue.pop(0)

        self.provider = ScriptedProvider(handler)

    def ask(self, message, conversation_id=None, cart_id=None):
        return _run(ag.process_message(
            self.db, "rest_demo_chezawa", conversation_id, message, self.provider,
            cart_id=cart_id))


def _j(message, tool=None, args=None):
    return json.dumps({"message": message, "tool": tool, "args": args or {}}, ensure_ascii=False)


@pytest.fixture
def harness_env(monkeypatch):
    def _make(replies):
        s = SharedCartSvc()
        h = AgentHarness(replies, s)
        monkeypatch.setattr(ag, "svc", s)
        monkeypatch.setattr(tools_mod, "svc", s)
        return h
    return _make


def _seed_conv(db, **over):
    c = {"_id": f"conv-doc-{len(db.ai_conversations.docs) + 1}",
         "conversation_id": over.pop("conversation_id", "conv-seed-1"),
         "restaurant_id": "rest-1", "cart_id": "cart-shared", "draft": {}, "customer": {},
         "order_reference": None, "messages": []}
    c.update(over)
    db.ai_conversations.docs.append(c)
    return c


# =============== 1. Compatibility: no cart_id = historical behavior ===============
def test_chat_without_cart_id_keeps_historical_behavior(harness_env):
    h = harness_env([_j("Bonjour et bienvenue !")])
    out = h.ask("Bonjour")
    assert out["conversation_id"]
    assert len(h.svc.created_carts) == 1  # a dedicated cart was created
    assert out["cart_id"] == h.svc.created_carts[0]
    conv = h.db.ai_conversations.docs[0]
    assert conv["cart_id"] == out["cart_id"]


# =============== 2. New conversation linked to a valid shared cart ===============
def test_new_conversation_with_valid_cart_id_links_without_second_cart(harness_env):
    h = harness_env([_j("Bonjour ! Que souhaitez-vous commander ?")])
    out = h.ask("Bonjour", cart_id="cart-shared")
    assert out["cart_id"] == "cart-shared"
    assert h.svc.created_carts == []  # NO second cart was created
    assert h.db.ai_conversations.docs[0]["cart_id"] == "cart-shared"


# =============== 3-5. Server-side cart validation ===============
def test_cart_of_other_restaurant_is_404_and_no_conversation_created(harness_env):
    h = harness_env([_j("jamais appelé")])
    with pytest.raises(HTTPException) as e:
        h.ask("Bonjour", cart_id="cart-foreign")
    assert e.value.status_code == 404
    assert e.value.detail == "Panier introuvable"
    assert h.db.ai_conversations.docs == []
    assert h.provider_calls == 0  # the model is never reached on a bad cart


def test_unknown_cart_is_404_and_no_conversation_created(harness_env):
    h = harness_env([_j("jamais appelé")])
    with pytest.raises(HTTPException) as e:
        h.ask("Bonjour", cart_id="cart-nope")
    assert e.value.status_code == 404
    assert h.db.ai_conversations.docs == []


def test_ordered_cart_is_409_for_new_conversation(harness_env):
    h = harness_env([_j("jamais appelé")])
    with pytest.raises(HTTPException) as e:
        h.ask("Bonjour", cart_id="cart-ordered")
    assert e.value.status_code == 409
    assert "plus utilisable" in e.value.detail
    assert h.db.ai_conversations.docs == []


# =============== 6. Existing conversation, same cart ===============
def test_existing_conversation_with_same_cart_id_continues_normally(harness_env):
    h = harness_env([_j("Bonjour !")])
    _seed_conv(h.db, conversation_id="conv-seed-1", cart_id="cart-shared")
    out = h.ask("Bonjour", conversation_id="conv-seed-1", cart_id="cart-shared")
    assert out["conversation_id"] == "conv-seed-1"
    assert out["cart_id"] == "cart-shared"
    assert len(h.db.ai_conversations.docs) == 1  # no second conversation


# =============== 7-11. Re-association rules on an existing conversation ===============
def test_relink_to_open_nonempty_cart_is_409_and_cart_unchanged(harness_env):
    h = harness_env([_j("jamais appelé")])
    conv = _seed_conv(h.db, conversation_id="conv-seed-1", cart_id="cart-nonempty")
    with pytest.raises(HTTPException) as e:
        h.ask("Bonjour", conversation_id="conv-seed-1", cart_id="cart-shared")
    assert e.value.status_code == 409
    assert "panier avec des articles" in e.value.detail
    assert conv["cart_id"] == "cart-nonempty"  # never a silent switch


def test_relink_from_empty_open_cart_to_another_open_cart_allowed(harness_env):
    h = harness_env([_j("Bonjour !")])
    conv = _seed_conv(h.db, conversation_id="conv-seed-1", cart_id="cart-shared")
    out = h.ask("Bonjour", conversation_id="conv-seed-1", cart_id="cart-empty-b")
    assert out["cart_id"] == "cart-empty-b"
    assert conv["cart_id"] == "cart-empty-b"  # persisted on the stored document


def test_relink_after_visual_order_is_allowed(harness_env):
    """The shared cart was ordered through the visual checkout (cart is now
    "ordered") while the conversation holds no order_reference: switching to
    a fresh open cart must be allowed so the client can order again."""
    h = harness_env([_j("Bonjour !")])
    conv = _seed_conv(h.db, conversation_id="conv-seed-1", cart_id="cart-ordered")
    out = h.ask("Bonjour", conversation_id="conv-seed-1", cart_id="cart-shared")
    assert out["cart_id"] == "cart-shared"
    assert conv["cart_id"] == "cart-shared"


def test_conversation_with_order_reference_rejects_any_relink(harness_env):
    h = harness_env([_j("jamais appelé")])
    conv = _seed_conv(h.db, conversation_id="conv-seed-1", cart_id="cart-shared",
                      order_reference="CMD-2026-00001")
    with pytest.raises(HTTPException) as e:
        h.ask("Bonjour", conversation_id="conv-seed-1", cart_id="cart-empty-b")
    assert e.value.status_code == 409
    assert "déjà été créée" in e.value.detail
    assert conv["cart_id"] == "cart-shared"


def test_existing_conversation_foreign_cart_relink_is_404(harness_env):
    h = harness_env([_j("jamais appelé")])
    conv = _seed_conv(h.db, conversation_id="conv-seed-1", cart_id="cart-shared")
    with pytest.raises(HTTPException) as e:
        h.ask("Bonjour", conversation_id="conv-seed-1", cart_id="cart-foreign")
    assert e.value.status_code == 404
    assert conv["cart_id"] == "cart-shared"


def test_existing_conversation_ordered_cart_relink_is_409(harness_env):
    h = harness_env([_j("jamais appelé")])
    conv = _seed_conv(h.db, conversation_id="conv-seed-1", cart_id="cart-shared")
    with pytest.raises(HTTPException) as e:
        h.ask("Bonjour", conversation_id="conv-seed-1", cart_id="cart-ordered")
    assert e.value.status_code == 409
    assert conv["cart_id"] == "cart-shared"


# =============== 12-13. AI tools operate on the LINKED shared cart ===============
def test_ai_tool_mutates_the_linked_shared_cart(harness_env):
    h = harness_env([
        _j("Deux eaux minérales ajoutées.", tool="add_to_cart",
           args={"item_id": "eau", "quantity": 2}),
        _j("C'est bien dans votre panier."),
    ])
    out = h.ask("ajoute 2 eaux minérales", cart_id="cart-shared")
    assert out["cart_id"] == "cart-shared"
    assert len(out["cart"]["items"]) == 1
    assert out["cart"]["items"][0]["item_id"] == "eau"
    assert out["cart"]["items"][0]["quantity"] == 2
    # the SHARED cart document itself was mutated — visible to the visual menu
    lines = h.svc.carts["cart-shared"]["items"]
    assert len(lines) == 1
    assert lines[0]["item_id"] == "eau"
    assert lines[0]["quantity"] == 2
    assert h.svc.created_carts == []  # never fell back to a private cart


def test_second_turn_with_same_ids_stays_on_shared_cart(harness_env):
    h = harness_env([
        _j("Ajoutée.", tool="add_to_cart", args={"item_id": "eau", "quantity": 1}),
        _j("Une eau est dans votre panier."),
        _j("Vous avez exactement une eau minérale."),
    ])
    out1 = h.ask("ajoute une eau", cart_id="cart-shared")
    conv_id = out1["conversation_id"]
    out2 = h.ask("combien j'ai ?", conversation_id=conv_id, cart_id="cart-shared")
    assert out2["conversation_id"] == conv_id
    assert out2["cart_id"] == "cart-shared"
    assert len(h.svc.carts["cart-shared"]["items"]) == 1
    assert h.svc.created_carts == []


# =============== 14. Public catalogue carries image_url (REAL order_service) ===============
RID = "652f00000000000000000001"


class _Cursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: d.get(key) or 0, reverse=(direction == -1))
        return self

    async def to_list(self, limit):
        return self._docs[:limit]


class _Col:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def find(self, q=None):
        q = q or {}
        return _Cursor([d for d in self.docs if all(d.get(k) == v for k, v in q.items())])

    async def find_one(self, q):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                return d
        return None


class MenuDB:
    """In-memory collections for the REAL get_available_menu (D1.50 image_url)."""

    def __init__(self, items):
        self.menu_categories = _Col([{"_id": "cat-1", "restaurant_id": RID, "active": True,
                                      "display_order": 1, "name": "Plats"}])
        self.menu_option_groups = _Col()
        self.menu_options = _Col()
        self.menu_items = _Col(items)
        self.restaurants = _Col([{"_id": ObjectId(RID), "public_id": "rest_demo_chezawa",
                                  "name": "Chez Awa", "status": "active"}])


def _menu_item(**over):
    it = {"_id": "652f0000000000000000000b", "restaurant_id": RID, "category_id": "cat-1",
          "name": "Poulet braisé", "description": "Délicieux", "price": 5000, "active": True,
          "available": True, "display_order": 1, "option_group_ids": []}
    it.update(over)
    return it


def _first_item(data):
    return data["categories"][0]["items"][0]


def test_public_menu_items_include_image_url():
    db = MenuDB([_menu_item(image_url="https://cdn.example/poulet.png")])
    data = _run(real_svc.get_available_menu(db, RID))
    assert _first_item(data)["image_url"] == "https://cdn.example/poulet.png"


def test_image_url_falls_back_to_legacy_image_field():
    db = MenuDB([_menu_item(image="legacy/poulet.png")])
    data = _run(real_svc.get_available_menu(db, RID))
    assert _first_item(data)["image_url"] == "legacy/poulet.png"


def test_image_url_empty_when_item_has_no_image_at_all():
    db = MenuDB([_menu_item()])
    data = _run(real_svc.get_available_menu(db, RID))
    assert _first_item(data)["image_url"] == ""


def test_image_url_prefers_current_field_over_legacy_image():
    db = MenuDB([_menu_item(image_url="https://cdn.example/new.png", image="old.png")])
    data = _run(real_svc.get_available_menu(db, RID))
    assert _first_item(data)["image_url"] == "https://cdn.example/new.png"
