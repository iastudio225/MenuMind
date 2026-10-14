"""
RestoIA D1.21 — Agent orchestration tests (mocked services, no network, no real DB).

Covers: greeting/question scenarios without useless tool calls, updated-data
tool routing, server-side prices/totals, order path with hard guards, tool
error feedback, MAX_STEPS bound, provider contract, and menu loading once
per turn (D1.21 optimization).
"""
import json

import pytest
from fastapi import HTTPException

from services.ai import agent_service as ag
from services.ai import quota
from services.ai import tools as tools_mod
from services.ai.provider import AIProvider, ScriptedProvider


def _run(coro):
    import asyncio
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _fresh_quota():
    """D1.22: in-memory quotas persist across tests — reset per test."""
    quota.reset()
    yield
    quota.reset()


# =============== Fakes ===============
class FakeDB:
    def __init__(self):
        self.ai_conversations = self._ConvCol()
        self.orders = self._OrdersCol()

    class _ConvCol:
        def __init__(self):
            self.docs = []

        async def find_one(self, q):
            for d in self.docs:
                if all(d.get(k) == v for k, v in q.items()):
                    return d
            return None

        async def insert_one(self, doc):
            # emulate MongoDB: the driver mutates the dict with a fresh _id
            doc.setdefault("_id", f"oid-{len(self.docs) + 1}")
            self.docs.append(doc)

        async def update_one(self, q, update):
            doc = await self.find_one(q)
            if doc and "$set" in update:
                doc.update(update["$set"])

    class _OrdersCol:
        def __init__(self):
            self.docs = []

        async def find_one(self, q):
            for d in self.docs:
                if all(d.get(k) == v for k, v in q.items()):
                    return d
            return None


class FakeSvc:
    """Replaces services.order_service for agent+tools (call counters included)."""

    def __init__(self):
        self.menu_calls = 0
        self.zones_calls = 0
        self.add_calls = 0
        self.create_order_calls = []
        self.total = 12000  # server truth

    def now_iso(self):
        return "2026-10-09T12:00:00Z"

    async def get_restaurant_by_public_id(self, db, public_id):
        # mirrors order_service: unknown/inactive -> 404 before any quota
        if public_id != "rest_demo_chezawa":
            raise HTTPException(status_code=404, detail="Restaurant introuvable")
        return {"_id": "rest-1", "name": "Chez Awa", "public_id": public_id}

    async def create_cart(self, db, restaurant_id, session_id=None):
        return {"cart_id": "cart-1"}

    async def get_available_menu(self, db, restaurant_id):
        self.menu_calls += 1
        return {"categories": [{"id": "c1", "items": [
            {"id": "poulet", "name": "Poulet braisé", "price": 5000, "available": True}]}]}

    async def get_delivery_zones(self, db, restaurant_id, active_only=False):
        self.zones_calls += 1
        return [{"id": "z1", "name": "Cocody", "fee": 1000}]

    async def get_cart(self, db, cart_id, restaurant_id=None):
        return {"cart_id": cart_id, "items": []}

    async def calculate_cart(self, db, restaurant_id, cart, delivery_fee=0):
        return {"items": [], "subtotal": self.total - delivery_fee,
                "delivery_fee": delivery_fee, "total": self.total}

    async def add_to_cart(self, db, restaurant_id, cart, item_id, quantity, option_ids):
        if item_id == "inconnu":
            raise HTTPException(status_code=400, detail="Article introuvable dans le menu.")
        self.add_calls += 1
        return {"item_id": item_id, "quantity": quantity}

    async def update_cart_item(self, db, restaurant_id, cart, cart_item_id, quantity=None, option_ids=None):
        return {}

    async def remove_cart_item(self, db, cart, cart_item_id):
        return {}

    async def calculate_delivery_fee(self, db, restaurant_id, order_type, zone_id):
        return 1000 if zone_id == "z1" else 0

    async def validate_cart(self, db, restaurant_id, cart):
        return {"valid": True, "issues": []}

    async def create_order(self, db, restaurant_id, cart, customer_data, order_type,
                           delivery_zone_id=None, customer_note="", idempotency_key=None, created_by=None):
        order = {"reference": "CMD-TEST-1", "status": "PENDING", "total": self.total,
                 "tracking_token": "tok-1"}
        self.create_order_calls.append({"order_type": order_type, "total": order["total"]})
        return order


class AgentHarness:
    """Scripted model + counters around process_message."""

    def __init__(self, replies, fake_svc=None):
        self.svc = fake_svc or FakeSvc()
        self.db = FakeDB()
        self.prompts = []
        self.turns = []  # messages (transcript+turn_notes) seen by the model
        self.provider_calls = 0
        self.queue = list(replies)

        def handler(system_prompt, messages):
            self.provider_calls += 1
            self.prompts.append(system_prompt)
            self.turns.append(messages)
            if not self.queue:
                raise AssertionError(
                    f"model called {self.provider_calls} times, queue empty; prompts={len(self.prompts)}")
            return self.queue.pop(0)

        self.provider = ScriptedProvider(handler)

    def ask(self, message, conversation_id=None):
        return _run(ag.process_message(
            self.db, "rest_demo_chezawa", conversation_id, message, self.provider))

    @property
    def tool_calls(self):
        return self.svc.add_calls + len(self.svc.create_order_calls)


@pytest.fixture
def harness_env(monkeypatch):
    """Wire fakes into agent_service and tools (real execute_tool path)."""
    def _make(replies):
        h = AgentHarness(replies)
        monkeypatch.setattr(ag, "svc", h.svc)
        monkeypatch.setattr(tools_mod, "svc", h.svc)
        return h
    return _make


def _j(message, tool=None, args=None):
    return json.dumps({"message": message, "tool": tool, "args": args or {}}, ensure_ascii=False)


# =============== 1. Salutation: no useless tool ===============
def test_greeting_single_model_call_no_tool(harness_env):
    h = harness_env([_j("Bonjour et bienvenue ! Que souhaitez-vous commander ?")])
    out = h.ask("Bonjour")
    assert out["message"]
    assert h.provider_calls == 1
    assert h.tool_calls == 0
    assert h.svc.add_calls == 0 and not h.svc.create_order_calls


# =============== 2. Menu question answered from context ===============
def test_menu_question_uses_provided_context(harness_env):
    h = harness_env([_j("Le poulet braisé est à 5000 FCFA.")])
    out = h.ask("C'est combien le poulet ?")
    assert h.provider_calls == 1
    assert h.tool_calls == 0
    # the system prompt given to the model contains the menu reference
    assert "MENU DISPONIBLE" in h.prompts[0]
    assert "Poulet braisé" in h.prompts[0]


def test_prompt_instructs_not_to_re_read_menu_and_zones(harness_env):
    h = harness_env([_j("Bienvenue !")])
    h.ask("Bonjour")
    p = h.prompts[0]
    assert "get_available_menu" in p and "get_delivery_zones" in p
    assert "ne pas" in p.lower() and "déjà" in p.lower()
    assert "référence" in p.lower() or "suffisent" in p.lower() or "fourni" in p.lower()


def test_menu_loaded_once_per_turn(harness_env):
    """D1.21: menu fetched once before the loop, even across several steps."""
    h = harness_env([
        _j("Poulet ajouté.", tool="add_to_cart", args={"item_id": "poulet", "quantity": 1}),
        _j("C'est dans votre panier !"),
    ])
    h.ask("Ajoute un poulet braisé")
    assert h.provider_calls == 2
    assert h.svc.menu_calls == 1  # was one per step before D1.21


# =============== 3. Updated data still uses the tool ===============
def test_add_to_cart_routes_through_tool(harness_env):
    h = harness_env([
        _j("Ajout en cours.", tool="add_to_cart", args={"item_id": "poulet", "quantity": 2}),
        _j("Ajouté x2."),
    ])
    out = h.ask("Je veux 2 poulets braisés")
    assert h.svc.add_calls == 1
    assert h.provider_calls == 2
    assert out["message"] == "Ajouté x2."


def test_zones_still_callable_when_needed(harness_env):
    h = harness_env([
        _j("Je vérifie.", tool="get_delivery_zones", args={}),
        _j("Zone Cocody : frais 1000 FCFA."),
    ])
    h.ask("Quelles sont les zones ?")
    assert h.svc.zones_calls >= 1  # tool preserved, not removed


# =============== 4. Prices/totals from backend ===============
def test_total_comes_from_backend_not_model(harness_env):
    h = harness_env([_j("Le total est de 999 FCFA.")])
    out = h.ask("C'est combien au total ?")
    assert out["cart"]["total"] == 12000  # FakeSvc server truth
    assert out["cart"]["total"] != 999


# =============== 5. Order path preserved ===============
def test_order_path_with_explicit_confirmation(harness_env):
    # turns: [tool reply, final reply] except one final-only turn
    h = harness_env([
        _j("Quelle zone ?", tool="set_fulfillment",
           args={"order_type": "DELIVERY", "delivery_zone_id": "z1"}),
        _j("Livraison Cocody enregistrée."),
        _j("Vos infos ?", tool="set_customer",
           args={"first_name": "Jean", "phone": "0707070707"}),
        _j("Client enregistré."),
        _j("Calcul du panier.", tool="calculate_cart", args={}),
        _j("Voici le récapitulatif : total 12000 FCFA. Confirmez-vous ?"),
        _j("Voici le récapitulatif : total 12000 FCFA. Confirmez-vous ?"),
        _j("Commande créée !", tool="create_order", args={}),
        _j("Commande CMD-TEST-1 confirmée."),
    ])
    conv = None
    out = h.ask("Je voudrais commander un poulet", conv)
    conv = out["conversation_id"]
    out = h.ask("livraison Cocody", conv)
    out = h.ask("Jean, 0707070707", conv)
    out = h.ask("présente le récapitulatif", conv)
    out = h.ask("je confirme", conv)
    assert out["order"] is not None
    assert out["order"]["reference"] == "CMD-TEST-1"
    assert out["order"]["total"] == 12000  # server price
    assert h.svc.create_order_calls[0]["total"] == 12000


def test_order_without_confirmation_is_blocked(harness_env):
    h = harness_env([
        _j("Tentative.", tool="create_order", args={}),
        _j("Confirmation requise pour continuer."),
    ])
    out = h.ask("bonjour")
    assert out["order"] is None
    assert not h.svc.create_order_calls  # hard guard AFFIRM in tools.py
    # tool error fed back to the model (in messages), not invented
    assert "Confirmation explicite" in json.dumps(h.turns[-1], ensure_ascii=False)


# =============== 6. Tool error handled cleanly ===============
def test_tool_error_feedback_without_invention(harness_env):
    h = harness_env([
        _j("Tentative.", tool="add_to_cart", args={"item_id": "inconnu", "quantity": 1}),
        _j("Cet article n'est pas disponible."),
    ])
    out = h.ask("Ajoute l'article inconnu")
    assert h.svc.add_calls == 0
    assert h.provider_calls == 2  # model recalled with the error
    assert "Article introuvable" in json.dumps(h.turns[-1], ensure_ascii=False)
    assert out["message"] == "Cet article n'est pas disponible."


# =============== 7. MAX_STEPS bound ===============
def test_max_steps_never_exceeded(harness_env):
    h = harness_env([])

    def always_tool(system_prompt, messages):
        h.provider_calls += 1
        h.prompts.append(system_prompt)
        return _j("étape", tool="calculate_cart", args={})

    h.provider = ScriptedProvider(always_tool)
    out = h.ask("boucle")
    assert h.provider_calls == 6  # MAX_STEPS, never more
    assert out["message"]  # fallback message provided


# =============== 8. Provider contract unchanged ===============
def test_provider_contract_unchanged():
    assert issubclass(ScriptedProvider, AIProvider)
    import inspect
    sig = inspect.signature(AIProvider.generate)
    assert list(sig.parameters) == ["self", "system_prompt", "messages"]


# =============== Prompt safety: business rules untouched ===============
def test_business_rules_still_in_prompt(harness_env):
    h = harness_env([_j("OK")])
    h.ask("Bonjour")
    p = h.prompts[0]
    assert "RÈGLES ABSOLUES" in p
    assert "jamais" in p.lower()
    assert "confirmation explicite" in p.lower()
    assert "BACKEND est la seule source de vérité" in p
