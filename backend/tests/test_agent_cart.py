"""
MenuMind D1.46 — AI cart integrity (mocked services, no network, no real DB).

Reproduces then covers the two anomalies reported on the launch widget:

1. DUPLICATES — order_service.add_to_cart always $push-es a new line (shared
   with the classic checkout). When the model adds an article already on a
   line (re-add after a mid-turn failure, "j'en prends encore un"...), the
   cart ended up with two identical lines. Fix lives in services/ai/tools.py:
   identical item + identical options cumulate on the existing line.

2. LOST/PHANTOM LINES — order_service.remove_cart_item is an unchecked $pull:
   a wrong cart_item_id (model passing the menu item_id, a stale id...)
   silently no-ops while the tool reports success, so the model announces a
   removal that never happened and the recap diverges from the cart. Fix in
   tools.py: validate the cart_item_id first, raise a controlled 404 the
   model can act on (same contract as update_cart_item).

order_service/cart_router (classic checkout) keep their own contracts,
covered by tests/test_orders.py. The fakes below keep the LEGACY
order_service semantics (push-always add, unchecked pull remove, validating update) on
purpose: every assertion then exercises the tools/agent layer alone. The
REAL order_service now merges identical lines itself since the étape 22
P1-a fix (covered in tests/test_order_integrity.py, RealSvcDB section).
"""
import json

import pytest
from fastapi import HTTPException

from services.ai import agent_service as ag
from services.ai import quota
from services.ai import tools as tools_mod
from services.ai.provider import ScriptedProvider

PRICES = {"eau": 500, "coca": 700, "poulet": 5000}


def _run(coro):
    import asyncio
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _fresh_quota():
    quota.reset()
    yield
    quota.reset()


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


class CartSvc:
    """Stateful fake mirroring the real order_service cart semantics exactly."""

    def __init__(self):
        self.cart = {"_id": "cart-doc-1", "cart_id": "cart-1",
                     "restaurant_id": "rest-1", "items": []}
        self.menu_calls = 0
        self.zones_calls = 0
        self.add_calls = 0

    def now_iso(self):
        return "2026-10-16T12:00:00Z"

    async def get_restaurant_by_public_id(self, db, public_id):
        if public_id != "rest_demo_chezawa":
            raise HTTPException(status_code=404, detail="Restaurant introuvable")
        return {"_id": "rest-1", "name": "Chez Awa", "public_id": public_id}

    async def create_cart(self, db, restaurant_id, session_id=None):
        return {"cart_id": "cart-1"}

    async def get_available_menu(self, db, restaurant_id):
        self.menu_calls += 1
        return {"restaurant": {"public_id": "rest_demo_chezawa", "name": "Chez Awa"},
                "categories": [{"id": "c1", "name": "Boissons", "items": [
                    {"id": "eau", "name": "Eau minérale", "price": PRICES["eau"], "available": True, "options": []},
                    {"id": "coca", "name": "Coca", "price": PRICES["coca"], "available": True, "options": []},
                    {"id": "poulet", "name": "Poulet braisé", "price": PRICES["poulet"], "available": True, "options": []},
                ]}]}

    async def get_delivery_zones(self, db, restaurant_id, active_only=False):
        self.zones_calls += 1
        return [{"id": "z1", "name": "Cocody", "fee": 1000}]

    async def get_cart(self, db, cart_id, restaurant_id=None):
        c = dict(self.cart)
        c["cart_id"] = cart_id
        c["items"] = [dict(i) for i in self.cart["items"]]
        return c

    async def add_to_cart(self, db, restaurant_id, cart, item_id, quantity, option_ids):
        # push-always on purpose: the tool-layer merge must hold alone
        # (the REAL service merges identical lines since étape 22 P1-a)
        if item_id not in PRICES:
            raise HTTPException(status_code=400, detail="Article introuvable dans le menu.")
        if quantity < 1:
            raise HTTPException(status_code=400, detail="Quantité invalide")
        self.add_calls += 1
        self.cart["items"].append({
            "cart_item_id": f"ci-{len(self.cart['items']) + 1}",
            "item_id": item_id,
            "quantity": int(quantity),
            "option_ids": list(option_ids or []),
            "expected_unit_price": PRICES[item_id],
            "expected_options_total": 0,
        })
        return await self.get_cart(db, self.cart["cart_id"])

    async def update_cart_item(self, db, restaurant_id, cart, cart_item_id,
                               quantity=None, option_ids=None):
        # mirrors order_service.update_cart_item: 404 on unknown line
        line = next((i for i in self.cart["items"] if i["cart_item_id"] == cart_item_id), None)
        if not line:
            raise HTTPException(status_code=404, detail="Ligne de panier introuvable")
        if quantity is not None:
            if quantity < 1:
                raise HTTPException(status_code=400, detail="Quantité invalide")
            line["quantity"] = int(quantity)
        if option_ids is not None:
            line["option_ids"] = list(option_ids)
        return await self.get_cart(db, self.cart["cart_id"])

    async def remove_cart_item(self, db, cart, cart_item_id):
        # mirrors order_service.remove_cart_item: unchecked pull (silent no-op)
        self.cart["items"] = [i for i in self.cart["items"]
                              if i["cart_item_id"] != cart_item_id]
        return await self.get_cart(db, self.cart["cart_id"])

    async def calculate_cart(self, db, restaurant_id, cart, delivery_fee=0, discount=0):
        lines, subtotal = [], 0
        for ci in cart.get("items", []):
            unit = PRICES.get(ci["item_id"], 0)
            line_total = unit * int(ci["quantity"])
            subtotal += line_total
            lines.append({"cart_item_id": ci["cart_item_id"], "item_id": ci["item_id"],
                          "name": ci["item_id"], "quantity": ci["quantity"],
                          "unit_price": unit, "options": ci.get("option_ids", []),
                          "line_total": line_total, "available": True})
        return {"items": lines, "subtotal": subtotal, "delivery_fee": int(delivery_fee),
                "discount": 0, "total": max(subtotal + int(delivery_fee), 0)}


def _conv(**over):
    c = {"_id": "conv-doc-1", "conversation_id": "conv-1", "restaurant_id": "rest-1",
         "cart_id": "cart-1", "draft": {}, "customer": {}, "order_reference": None,
         "messages": []}
    c.update(over)
    return c


def _j(message, tool=None, args=None):
    return json.dumps({"message": message, "tool": tool, "args": args or {}}, ensure_ascii=False)


@pytest.fixture
def cart(monkeypatch):
    s = CartSvc()
    monkeypatch.setattr(tools_mod, "svc", s)
    return s


@pytest.fixture
def harness_env(monkeypatch):
    def _make(replies):
        s = CartSvc()
        h = AgentHarness(replies, s)
        monkeypatch.setattr(ag, "svc", s)
        monkeypatch.setattr(tools_mod, "svc", s)
        return h
    return _make


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

    def ask(self, message, conversation_id=None):
        return _run(ag.process_message(
            self.db, "rest_demo_chezawa", conversation_id, message, self.provider))


def _tool(tool, args, db=None, conv=None):
    return _run(tools_mod.execute_tool(db or FakeDB(), conv or _conv(), tool, args, "test"))


# =============== 1. Duplicates: cumulate, never double-push ===============
def test_add_same_article_twice_merges_into_single_line(cart):
    """Repro D1.46: pre-fix this produced 2 lines of eau qty 1."""
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1})
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1})
    items = cart.cart["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 2


def test_add_accumulates_quantities_on_existing_line(cart):
    _tool("add_to_cart", {"item_id": "poulet", "quantity": 1})
    _tool("add_to_cart", {"item_id": "poulet", "quantity": 2})
    items = cart.cart["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 3


def test_different_options_stay_separate_lines(cart):
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1, "option_ids": ["froide"]})
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1, "option_ids": ["plate"]})
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1, "option_ids": []})
    items = cart.cart["items"]
    assert len(items) == 3
    assert all(i["quantity"] == 1 for i in items)


def test_option_order_does_not_block_merge(cart):
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1, "option_ids": ["a", "b"]})
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1, "option_ids": ["b", "a"]})
    items = cart.cart["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 2


def test_add_rejects_invalid_quantity_without_mutation(cart):
    with pytest.raises(HTTPException) as e:
        _tool("add_to_cart", {"item_id": "eau", "quantity": "abc"})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _tool("add_to_cart", {"item_id": "eau", "quantity": 0})
    assert e.value.status_code == 400
    assert cart.cart["items"] == []


# =============== 2. Removal: validate before the silent $pull ===============
def test_remove_unknown_line_id_raises_404_and_keeps_cart(cart):
    """Repro D1.46: pre-fix this silently succeeded and reported the cart."""
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1})
    with pytest.raises(HTTPException) as e:
        _tool("remove_from_cart", {"cart_item_id": "ci-999"})
    assert e.value.status_code == 404
    assert "Ligne de panier introuvable" in e.value.detail
    assert len(cart.cart["items"]) == 1


def test_remove_with_menu_item_id_instead_of_cart_item_id_rejected(cart):
    """Repro D1.46: the model's typical confusion (item_id instead of cart_item_id)."""
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1})
    _tool("add_to_cart", {"item_id": "coca", "quantity": 1})
    with pytest.raises(HTTPException) as e:
        _tool("remove_from_cart", {"cart_item_id": "coca"})
    assert e.value.status_code == 404
    assert len(cart.cart["items"]) == 2


def test_remove_missing_cart_item_id_arg_is_controlled_400(cart):
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1})
    with pytest.raises(HTTPException) as e:
        _tool("remove_from_cart", {"item_id": "eau"})
    assert e.value.status_code == 400
    assert len(cart.cart["items"]) == 1


def test_valid_remove_deletes_only_target_line(cart):
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1})
    _tool("add_to_cart", {"item_id": "coca", "quantity": 2})
    assert cart.cart["items"][0]["cart_item_id"] == "ci-1"
    _tool("remove_from_cart", {"cart_item_id": "ci-1"})
    items = cart.cart["items"]
    assert len(items) == 1
    assert items[0]["item_id"] == "coca"
    assert items[0]["quantity"] == 2


# =============== 3. Partial removal via update (prompt contract) ===============
def test_update_remaining_quantity_for_partial_removal(cart):
    _tool("add_to_cart", {"item_id": "coca", "quantity": 3})
    _tool("update_cart_item", {"cart_item_id": "ci-1", "quantity": 2})
    assert cart.cart["items"][0]["quantity"] == 2
    with pytest.raises(HTTPException) as e:
        _tool("update_cart_item", {"cart_item_id": "ci-1", "quantity": 0})
    assert e.value.status_code == 400
    assert cart.cart["items"][0]["quantity"] == 2


# =============== 4. Agent level: full process_message flows ===============
def test_agent_readd_same_article_across_turns_does_not_duplicate(harness_env):
    """Repro D1.46: two turns each adding an eau -> one line qty 2, not two lines."""
    h = harness_env([
        _j("Eau ajoutée.", tool="add_to_cart", args={"item_id": "eau", "quantity": 1}),
        _j("Une eau est dans votre panier."),
        _j("Ajoutée.", tool="add_to_cart", args={"item_id": "eau", "quantity": 1}),
        _j("Vous avez 2 eaux."),
    ])
    out = h.ask("une eau")
    conv = out["conversation_id"]
    out = h.ask("j'en prends une autre", conv)
    assert len(out["cart"]["items"]) == 1
    assert out["cart"]["items"][0]["quantity"] == 2
    lines = h.svc.cart["items"]
    assert len(lines) == 1
    assert lines[0]["item_id"] == "eau"
    assert lines[0]["quantity"] == 2


def test_agent_remove_wrong_id_gets_error_feedback_then_recovers(harness_env):
    """Repro D1.46: wrong id must surface a tool error, then a valid retry works."""
    h = harness_env([
        _j("Retrait.", tool="remove_from_cart", args={"cart_item_id": "coca"}),
        _j("Correction.", tool="remove_from_cart", args={"cart_item_id": "ci-2"}),
        _j("Le Coca a été retiré."),
    ])
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1}, db=h.db)
    _tool("add_to_cart", {"item_id": "coca", "quantity": 1}, db=h.db)
    out = h.ask("enlève le coca")
    assert "Ligne de panier introuvable" in json.dumps(h.turns[1], ensure_ascii=False)
    assert out["message"] == "Le Coca a été retiré."
    lines = h.svc.cart["items"]
    assert len(lines) == 1
    assert lines[0]["item_id"] == "eau"


def test_agent_claimed_removal_on_unknown_line_never_reports_success(harness_env):
    """Pre-fix: the tool reported a success cart view while the line was still there."""
    h = harness_env([
        _j("Retiré !", tool="remove_from_cart", args={"cart_item_id": "ci-999"}),
        _j("La ligne demandée n'existe pas dans votre panier."),
    ])
    _tool("add_to_cart", {"item_id": "eau", "quantity": 1}, db=h.db)
    out = h.ask("enlève ci-999")
    assert out["message"] == "La ligne demandée n'existe pas dans votre panier."
    tool_notes = [m for m in h.turns[1] if m.get("role") == "tool"]
    assert json.loads(tool_notes[0]["content"]).get("error") == "Ligne de panier introuvable"
    assert len(h.svc.cart["items"]) == 1


# =============== 5. Prompt instructs the corrected tool usage ===============
def test_prompt_documents_cumulation_and_cart_item_id(harness_env):
    """Repro D1.46: pre-fix the prompt said neither cumulation nor line-id rules."""
    h = harness_env([_j("Bonjour !")])
    h.ask("Bonjour")
    p = h.prompts[0]
    assert "cumulée sur la ligne existante" in p
    assert "quantité RESTANTE" in p
    assert "cart_item_id fourni dans la section PANIER" in p
    assert "jamais un item_id du menu" in p


# =============== 6. set_customer — non-destructive merge (étape 24 P1) ===============
def _customer_tool(args, conv=None, db=None):
    db = db or FakeDB()
    conv = conv or _conv()
    db.ai_conversations.docs.append(conv)
    return _run(tools_mod.execute_tool(db, conv, "set_customer", args, "infos")), db, conv


def test_set_customer_full_update_persists_and_returns_model_view(cart):
    (result, extra), db, conv = _customer_tool({
        "first_name": "Fred", "last_name": "POUPOUYA",
        "phone": "0708000001", "email": "fred@example.ci"})
    assert extra is None
    assert result == {"customer": {"last_name": "POUPOUYA", "first_name": "Fred",
                                   "contact": "enregistré"}}
    assert conv["customer"]["first_name"] == "Fred"
    assert conv["customer"]["phone"] == "0708000001"
    assert db.ai_conversations.docs[0]["customer"]["email"] == "fred@example.ci"


def test_set_customer_first_name_only_keeps_existing_fields(cart):
    conv = _conv(customer={"first_name": "Fred", "last_name": "POUPOUYA",
                           "phone": "0708000001", "email": ""})
    (result, _), _, _ = _customer_tool({"first_name": "Alfred"}, conv=conv)
    assert conv["customer"] == {"first_name": "Alfred", "last_name": "POUPOUYA",
                                "phone": "0708000001", "email": ""}
    assert result["customer"]["first_name"] == "Alfred"
    assert result["customer"]["last_name"] == "POUPOUYA"


def test_set_customer_last_name_only_keeps_first_name(cart):
    """Audit étape 23 C3: a nom-only call must never erase the known prénom."""
    conv = _conv(customer={"first_name": "Fred", "last_name": "POUPOUYA",
                           "phone": "0708000001", "email": ""})
    _customer_tool({"last_name": "KOUASSI"}, conv=conv)
    assert conv["customer"] == {"first_name": "Fred", "last_name": "KOUASSI",
                                "phone": "0708000001", "email": ""}


def test_set_customer_phone_only_keeps_names(cart):
    conv = _conv(customer={"first_name": "Fred", "last_name": "POUPOUYA",
                           "phone": "", "email": ""})
    _customer_tool({"phone": "0708000099"}, conv=conv)
    assert conv["customer"] == {"first_name": "Fred", "last_name": "POUPOUYA",
                                "phone": "0708000099", "email": ""}


def test_set_customer_blank_and_whitespace_fields_are_ignored_and_stripped(cart):
    conv = _conv(customer={"first_name": "Fred", "last_name": "POUPOUYA",
                           "phone": "0708000001", "email": ""})
    _customer_tool({"first_name": "", "last_name": "   KOUASSI   ", "email": "  "}, conv=conv)
    assert conv["customer"] == {"first_name": "Fred", "last_name": "KOUASSI",
                                "phone": "0708000001", "email": ""}


def test_set_customer_no_usable_field_is_400_and_mutates_nothing(cart):
    conv = _conv(customer={"first_name": "Fred", "last_name": "POUPOUYA",
                           "phone": "0708000001", "email": ""})
    db = FakeDB()
    db.ai_conversations.docs.append(conv)
    with pytest.raises(HTTPException) as e:
        _tool("set_customer", {"first_name": "", "last_name": "   ", "phone": None},
              db=db, conv=conv)
    assert e.value.status_code == 400
    assert e.value.detail == "Aucune information à enregistrer."
    assert conv["customer"] == {"first_name": "Fred", "last_name": "POUPOUYA",
                                "phone": "0708000001", "email": ""}
    assert db.ai_conversations.docs[0]["customer"] == conv["customer"]


def test_set_customer_successive_partial_updates_keep_full_profile(cart):
    (result, _), _, conv = _customer_tool({
        "first_name": "Fred", "last_name": "POUPOUYA", "phone": "0708000001"})
    _customer_tool({"last_name": "KOUASSI"}, conv=conv)
    _customer_tool({"first_name": "François"}, conv=conv)
    _customer_tool({"phone": "0708000002"}, conv=conv)
    assert conv["customer"] == {"first_name": "François", "last_name": "KOUASSI",
                                "phone": "0708000002"}
    assert result["customer"]["contact"] == "enregistré"


def test_set_customer_update_targets_only_its_conversation(cart):
    db = FakeDB()
    conv_a = _conv()
    conv_b = _conv(_id="conv-doc-2", conversation_id="conv-2")
    db.ai_conversations.docs.extend([conv_a, conv_b])
    _tool("set_customer", {"first_name": "Fred"}, db=db, conv=conv_a)
    assert conv_a["customer"] == {"first_name": "Fred"}
    assert conv_b["customer"] == {}
    assert db.ai_conversations.docs[0]["customer"] == {"first_name": "Fred"}
    assert db.ai_conversations.docs[1]["customer"] == {}


def test_set_customer_empty_args_object_is_controlled_400(cart):
    conv = _conv(customer={"first_name": "Fred"})
    with pytest.raises(HTTPException) as e:
        _tool("set_customer", {}, conv=conv)
    assert e.value.status_code == 400
    assert "0708" not in e.value.detail and "Fred" not in e.value.detail
    assert conv["customer"] == {"first_name": "Fred"}
