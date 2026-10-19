"""D1.54 étape 3 — day menu & targeted recommendations in the agent (mocked).

Covers the mandated cases: active day menu served as structured cards by the
backend, absent/inactive menu asking for taste (never the full catalogue),
preference -> validated relevant selection, explicit full catalogue (bounded
pages), forged/unknown id, foreign id, unavailable product, plain reply with
no cards, existing response fields preserved + `products` added, and tool
registration/prompt gating.

No real MongoDB, no network, no paid AI call: a ScriptedProvider replays
canned model answers and every service call is faked.
"""
import json

import pytest

from services.ai import agent_service as ag
from services.ai import quota
from services.ai import tools as tools_mod
from services.ai.tools import TOOL_NAMES
from tests.test_agent_service import AgentHarness, FakeSvc, _j


@pytest.fixture(autouse=True)
def _fresh_quota():
    """In-memory quotas persist across tests — reset per test (module-local)."""
    quota.reset()
    yield
    quota.reset()


DAY_ACTIVE = {"day": "monday", "status": "active", "items": [
    {"id": "poulet", "name": "Poulet braisé", "description": "", "image_url": "https://img/p.jpg",
     "price": 5000, "available": True, "options": []},
    {"id": "poisson", "name": "Poisson braisé", "description": "", "image_url": "https://img/f.jpg",
     "price": 4000, "available": True, "options": []},
]}


def make_catalogue():
    """15 products: enough to force a second page (page size 12)."""
    items = [
        {"id": "poulet", "name": "Poulet braisé", "description": "", "image_url": "https://img/p.jpg",
         "price": 5000, "available": True, "options": []},
        {"id": "poisson", "name": "Poisson braisé", "description": "", "image_url": "https://img/f.jpg",
         "price": 4000, "available": True, "options": []},
        {"id": "attieke", "name": "Attiéké poisson", "description": "", "image_url": "https://img/a.jpg",
         "price": 3500, "available": False, "options": []},
    ]
    items += [{"id": f"plat-{i}", "name": f"Plat {i}", "description": "", "image_url": "",
               "price": 1000 + i, "available": True, "options": []} for i in range(4, 16)]
    assert len(items) == 15
    return {"categories": [{"id": "c1", "name": "Plats", "items": items}]}


class DaySvc(FakeSvc):
    """FakeSvc + D1.54 card tools, with day menu/catalogue under test control."""

    def __init__(self, day_menu=None, catalogue=None):
        super().__init__()
        self.day_menu_calls = 0
        self.day_menu = DAY_ACTIVE if day_menu is None else day_menu
        self.catalogue = make_catalogue() if catalogue is None else catalogue

    async def get_day_menu(self, db, restaurant_id, now=None):
        self.day_menu_calls += 1
        return dict(self.day_menu)

    async def get_available_menu(self, db, restaurant_id):
        self.menu_calls += 1
        return self.catalogue


@pytest.fixture
def harness(monkeypatch):
    """Wire DaySvc into agent_service AND tools (real execute_tool path)."""
    def _make(replies, svc=None):
        h = AgentHarness(replies, fake_svc=svc or DaySvc())
        monkeypatch.setattr(ag, "svc", h.svc)
        monkeypatch.setattr(tools_mod, "svc", h.svc)
        return h
    return _make


def _tool_error(h, index=-1):
    """Error string fed back to the model in the last tool message of a turn."""
    return json.loads(h.turns[index][-1]["content"]).get("error", "")


# =============== 1. Active day menu: structured cards from the backend =====
def test_day_menu_active_cards_served_by_backend(harness):
    h = harness([
        _j("Voici le menu du jour.", tool="get_day_menu", args={}),
        _j("Voici le menu du jour de ce lundi !"),
    ])
    out = h.ask("Quel est le menu du jour ?")
    assert h.svc.day_menu_calls == 1
    assert h.provider_calls == 2  # one tool round + drafting, no model selection
    # ids/names/prices come verbatim from the backend catalogue, not the model
    assert out["products"] == DAY_ACTIVE["items"]
    assert [p["id"] for p in out["products"]] == ["poulet", "poisson"]
    assert out["products"][0]["price"] == 5000
    assert out["products"][0]["image_url"] == "https://img/p.jpg"
    # the model received the cards inside the tool result
    assert "Poulet braisé" in json.dumps(h.turns[1], ensure_ascii=False)
    assert out["message"] == "Voici le menu du jour de ce lundi !"


# =============== 2-3. Absent / inactive: ask taste, never the catalogue ====
def test_day_menu_absent_asks_taste_no_catalogue(harness):
    svc = DaySvc(day_menu={"day": "monday", "status": "not_configured", "items": []})
    h = harness([
        _j("Bien sûr.", tool="get_day_menu", args={}),
        _j("Qu'aimeriez-vous manger aujourd'hui ?"),
    ], svc=svc)
    out = h.ask("Il y a un menu du jour ?")
    assert svc.day_menu_calls == 1
    assert out["products"] == []            # full catalogue never substituted
    assert out["message"] == "Qu'aimeriez-vous manger aujourd'hui ?"
    note = json.dumps(h.turns[1], ensure_ascii=False)
    assert "recommend_items" in note        # guidance: pick a taste first
    assert "Ne présente JAMAIS tout le catalogue" in note


def test_day_menu_inactive_asks_taste_no_catalogue(harness):
    svc = DaySvc(day_menu={"day": "monday", "status": "inactive", "items": []})
    h = harness([
        _j("Vérification.", tool="get_day_menu", args={}),
        _j("Pas de menu du jour active, qu'aimez-vous ?"),
    ], svc=svc)
    out = h.ask("menu du jour")
    assert out["products"] == []
    res = json.loads(h.turns[1][-1]["content"])
    assert res["status"] == "inactive" and res["products"] == []
    assert "désactivé" in res["hint"]


# =============== 4. Preference -> validated relevant selection ============
def test_preference_triggers_validated_recommendation(harness):
    h = harness([
        _j("Je choisis.", tool="recommend_items", args={"item_ids": ["poisson"]}),
        _j("Voici une belle sélection !"),
    ])
    out = h.ask("J'ai envie de poisson aujourd'hui")
    assert [p["id"] for p in out["products"]] == ["poisson"]
    assert out["products"][0]["price"] == 4000   # server price, verbatim card
    assert h.svc.add_calls == 0                  # a recommendation never mutates the cart


def test_recommendation_limited_to_six_ids(harness):
    ids = [f"plat-{i}" for i in range(4, 11)]  # 7 ids
    h = harness([
        _j("Choix.", tool="recommend_items", args={"item_ids": ids}),
        _j("Voici des idées."),
    ])
    out = h.ask(" Donne-moi plusieurs idées ")
    assert out["products"] == []
    assert "Trop de produits proposés" in _tool_error(h)


# =============== 5. Full catalogue: explicit request, bounded pages ========
def test_full_catalog_on_explicit_request_is_bounded(harness):
    h = harness([
        _j("Voici la première page.", tool="show_catalog", args={}),
        _j("Voici les premiers plats !"),
    ])
    out = h.ask("Montre-moi toute la carte s'il te plaît")
    assert len(out["products"]) == 12   # page bounded (15 products total)
    res = json.loads(h.turns[1][-1]["content"])
    assert res["total"] == 15 and res["total_pages"] == 2 and res["page"] == 0
    # prompt gates the tool: explicit request only
    p = h.prompts[0]
    assert "show_catalog" in p and "demande explicitement" in p


def test_full_catalog_second_page_on_request(harness):
    h = harness([
        _j("Suite.", tool="show_catalog", args={"page": 1}),
        _j("Voici la suite !"),
    ])
    out = h.ask("Montre-moi la suite")
    assert len(out["products"]) == 3
    assert [p["id"] for p in out["products"]] == ["plat-13", "plat-14", "plat-15"]


def test_full_catalog_page_out_of_range_feedback(harness):
    h = harness([
        _j("Page.", tool="show_catalog", args={"page": 9}),
        _j("Cette page n'existe pas."),
    ])
    out = h.ask("page 9 merci")
    assert out["products"] == []
    assert "Page hors limites" in _tool_error(h)


# =============== 6-7. Forged / unknown / foreign ids rejected =============
def test_unknown_item_id_rejected(harness):
    h = harness([
        _j("Regarde.", tool="recommend_items", args={"item_ids": ["ghost-invente"]}),
        _j("Je ne trouve pas cet article sur la carte."),
    ])
    out = h.ask("Ajoute le ghost")
    assert out["products"] == []
    assert _tool_error(h) == "Article introuvable pour ce restaurant"
    assert h.svc.add_calls == 0


def test_foreign_item_id_rejected_with_same_message(harness):
    from bson import ObjectId
    foreign = str(ObjectId())  # well-formed, absent from THIS catalogue
    h = harness([
        _j("Regarde.", tool="recommend_items", args={"item_ids": [foreign]}),
        _j("Cet article n'existe pas ici."),
    ])
    out = h.ask("Ajoute ce produit")
    assert out["products"] == []
    # identical wording to an unknown id: no cross-tenant existence oracle
    assert _tool_error(h) == "Article introuvable pour ce restaurant"


# =============== 8. Unavailable product never presented as orderable ======
def test_unavailable_product_excluded_and_explained(harness):
    h = harness([
        _j("Je vérifie.", tool="recommend_items", args={"item_ids": ["attieke", "poulet"]}),
        _j("L'attiéké est indisponible, le poulet est bien disponible."),
    ])
    out = h.ask("Je voudrais de l'attiéké et du poulet")
    assert [p["id"] for p in out["products"]] == ["poulet"]
    res = json.loads(h.turns[1][-1]["content"])
    assert res["unavailable"] == ["Attiéké poisson"]
    assert "indisponible" in res["hint"]
    assert "commandable" in res["hint"]


def test_unavailable_only_selection_returns_no_cards(harness):
    h = harness([
        _j("Regarde.", tool="recommend_items", args={"item_ids": ["attieke"]}),
        _j("Il est actuellement en rupture."),
    ])
    out = h.ask("Je veux de l'attiéké")
    assert out["products"] == []
    assert "Attiéké poisson" in json.dumps(h.turns[1], ensure_ascii=False)


# =============== 9-10. Plain reply + backward-compatible contract =========
def test_plain_reply_has_no_cards(harness):
    h = harness([_j("Bonjour et bienvenue ! Que souhaitez-vous commander ?")])
    out = h.ask("Bonjour")
    assert out["products"] == []
    assert h.svc.day_menu_calls == 0


def test_response_keeps_existing_fields_plus_products(harness):
    h = harness([_j("Bonjour !")])
    out = h.ask("Salut")
    assert {"conversation_id", "message", "cart", "cart_id", "order", "products"} <= set(out)
    assert out["order"] is None
    assert isinstance(out["products"], list) and out["products"] == []
    assert isinstance(out["cart"], dict) and out["cart"]["total"] == 12000
    assert out["conversation_id"] and out["cart_id"]


# =============== Registration & prompt gating ==============================
def test_new_tools_are_registered():
    assert {"get_day_menu", "recommend_items", "show_catalog"} <= set(TOOL_NAMES)


def test_prompt_gates_day_menu_and_recommendation(harness):
    h = harness([_j("OK")])
    h.ask("Bonjour")
    p = h.prompts[0]
    assert "get_day_menu" in p and "UNIQUEMENT" in p
    assert "recommend_items" in p and "6 ids" in p
    assert "ne présente jamais tout le catalogue" in p.lower()
