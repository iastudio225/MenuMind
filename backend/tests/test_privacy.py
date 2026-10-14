"""D1.23 — privacy audit tests: no PII to the model, logs clean, tenant
isolation, malformed model output, invalid business ops, quota kept.

Everything is mocked: no network, no real DB, no order created.
"""
import pytest
from fastapi import HTTPException

from services.ai import agent_service as ag
from services.ai import quota
from services.ai import tools as tools_mod
from services.ai.provider import ScriptedProvider
from tests.test_agent_service import AgentHarness, FakeDB, FakeSvc, _j, _run


@pytest.fixture(autouse=True)
def _fresh_quota():
    quota.reset()
    yield
    quota.reset()


class PrivacySvc(FakeSvc):
    """FakeSvc with a second tenant and zone validation like the real service."""

    _IDS = {"rest_demo_chezawa": "rest-1", "rest_demo_b": "rest-2"}

    async def get_restaurant_by_public_id(self, db, public_id):
        if public_id not in self._IDS:
            raise HTTPException(status_code=404, detail="Restaurant introuvable")
        return {"_id": self._IDS[public_id], "name": f"Resto {public_id}",
                "public_id": public_id}

    async def calculate_delivery_fee(self, db, restaurant_id, order_type, zone_id):
        if order_type == "DELIVERY" and zone_id not in ("z1",):
            raise HTTPException(status_code=400,
                                detail="Cette zone de livraison n'est pas encore desservie.")
        return 1000 if zone_id == "z1" else 0


@pytest.fixture
def env(monkeypatch):
    def _make(replies, svc=None):
        h = AgentHarness(replies, fake_svc=svc or PrivacySvc())
        monkeypatch.setattr(ag, "svc", h.svc)
        monkeypatch.setattr(tools_mod, "svc", h.svc)
        return h
    return _make


# ============ 1. Prompt: no phone/email ever sent to the model ============
def test_prompt_excludes_phone_and_email():
    prompt = ag._build_system_prompt(
        {"name": "Chez Awa"}, {"categories": []}, [], {"total": 0}, {},
        {"first_name": "Jeanne", "last_name": "KOUASSI",
         "phone": "0707070707", "email": "jeanne@example.ci"}, False)
    section = prompt.split("CLIENT CONNU :")[1]
    # actual contact values never reach the model
    assert "0707070707" not in prompt
    assert "jeanne@example.ci" not in prompt
    # nor does the customer section carry phone/email fields
    # (the set_customer arg schema in the tool docs is not PII)
    assert '"phone"' not in section and '"email"' not in section
    assert "KOUASSI" in prompt          # family name kept for polite address
    assert "Jeanne" in prompt           # first name kept
    assert "enregistré" in prompt       # neutral contact marker


def test_prompt_customer_object_family_name_first():
    prompt = ag._build_system_prompt(
        {"name": "Chez Awa"}, {"categories": []}, [], {"total": 0}, {},
        {"first_name": "Jeanne", "last_name": "KOUASSI",
         "phone": "0707070707", "email": ""}, False)
    section = prompt.split("CLIENT CONNU :")[1]
    # section is serialized last_name then first_name, never the reverse
    assert '"last_name"' in section
    assert section.index('"last_name"') < section.index('"first_name"')
    # instruction: family name before first name, never inverted
    assert "NOM DE FAMILLE EN MAJUSCULES AVANT le prénom" in prompt
    assert "Ne jamais inverser" in prompt
    assert "KOUASSI Jeanne" in prompt


def test_prompt_empty_customer_is_clean():
    prompt = ag._build_system_prompt(
        {"name": "Chez Awa"}, {"categories": []}, [], {"total": 0}, {}, {}, False)
    assert '"contact"' not in prompt.split("CLIENT CONNU")[1]


# ============ 2. Tool result back to the model is redacted ============
def test_set_customer_result_redacted_for_model_persisted_in_db(env):
    h = env([
        _j("Client enregistré.",
           tool="set_customer",
           args={"first_name": "Jeanne", "last_name": "KOUASSI",
                 "phone": "0707070707", "email": "jeanne@example.ci"}),
        _j("Vos coordonnées sont enregistrées, KOUASSI Jeanne."),
    ])
    out = h.ask("Je suis KOUASSI Jeanne, 0707070707, jeanne@example.ci")
    assert out["message"]

    # the tool note seen by the model in the next step has no phone/email
    tool_notes = [m for m in h.turns[1] if m.get("role") == "tool"]
    flat = str(tool_notes)
    assert "0707070707" not in flat
    assert "jeanne@example.ci" not in flat
    assert "enregistré" in flat

    # persistence still holds the full record for order creation (D1.23: no
    # storage policy change)
    doc = h.db.ai_conversations.docs[0]["customer"]
    assert doc["phone"] == "0707070707"
    assert doc["email"] == "jeanne@example.ci"
    assert doc["last_name"] == "KOUASSI"


# ============ 3. Logs contain no PII, no prompt, no secret ============
def test_logs_free_of_pii_and_secrets(env, caplog):
    h = env([
        _j("Client enregistré.",
           tool="set_customer",
           args={"first_name": "Jeanne", "last_name": "KOUASSI",
                 "phone": "0707070707", "email": "jeanne@example.ci"}),
        _j("Tentative.", tool="add_to_cart",
           args={"item_id": "inconnu", "quantity": 1}),
        _j("Article indisponible."),
    ], svc=PrivacySvc())
    with caplog.at_level("INFO"):
        h.ask("Je suis KOUASSI Jeanne, 0707070707, jeanne@example.ci, un poulet")
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert caplog.records, "expected AI logs on this flow"
    for secret in ("0707070707", "jeanne@example.ci", "KOUASSI Jeanne",
                   "un poulet", "poulet", "GEMINI_API_KEY", "prompt"):
        assert secret not in joined
    # events still traceable (ids, tool names — no content)
    assert any("TOOL_CALLED" in r.getMessage() for r in caplog.records)


# ============ 4. Tenant isolation between restaurants ============
def test_conversation_from_other_restaurant_is_neutralized(env):
    h_a = env([_j("Bonjour KOUASSI Jeanne !")], svc=PrivacySvc())
    out_a = h_a.ask("message SECRET-resto-A")
    conv_a = out_a["conversation_id"]
    assert any(m["content"] == "message SECRET-resto-A"
               for m in h_a.db.ai_conversations.docs[0]["messages"])

    h_b = env([_j("Bonjour !")], svc=h_a.svc)  # same DB, other restaurant
    out_b = _run(ag.process_message(h_a.db, "rest_demo_b", conv_a,
                                    "message B", h_b.provider))
    conv_b_id = out_b["conversation_id"]
    assert conv_b_id != conv_a  # foreign conversation refused -> fresh one

    doc_b = next(d for d in h_a.db.ai_conversations.docs
                 if d["conversation_id"] == conv_b_id)
    assert doc_b["restaurant_id"] == "rest-2"
    assert all("SECRET-resto-A" not in m["content"] for m in doc_b["messages"])

    # original conversation untouched by the foreign attempt
    doc_a = next(d for d in h_a.db.ai_conversations.docs
                 if d["conversation_id"] == conv_a)
    assert doc_a["restaurant_id"] == "rest-1"
    assert all("message B" not in m["content"] for m in doc_a["messages"])


# ============ 5. Malformed model output handled safely ============
def test_malformed_model_output_never_crashes():
    prose = ag._parse_action("Désolé, je ne peux pas produire de JSON.")
    assert prose["tool"] is None and prose["message"]

    broken = ag._parse_action('{"message": "salut", "tool": ')
    assert broken["tool"] is None

    empty = ag._parse_action("")
    assert empty["tool"] is None and empty["message"]

    fenced = ag._parse_action('```json\n{"message": "ok", "tool": null}\n```')
    assert fenced["tool"] is None and fenced["message"] == "ok"


def test_unknown_tool_is_refused_cleanly(env):
    h = env([
        _j("Action.", tool="delete_all_orders", args={}),
        _j("Cette action n'est pas disponible."),
    ])
    out = h.ask("supprime toutes les commandes")
    assert out["message"] == "Cette action n'est pas disponible."
    assert "Outil inconnu" in str(h.turns[1])


# ============ 6. Invalid business operation refused properly ============
def test_unknown_delivery_zone_refused_by_server(env):
    h = env([
        _j("Zone en cours.", tool="set_fulfillment",
           args={"order_type": "DELIVERY", "delivery_zone_id": "zone_fantome"}),
        _j("Cette zone n'est pas desservie."),
    ])
    out = h.ask("livraison zone fantome")
    assert out["message"] == "Cette zone n'est pas desservie."
    assert not h.svc.create_order_calls
    assert "pas encore desservie" in str(h.turns[1])


def test_prices_come_from_server_even_if_model_sends_money(env):
    h = env([
        _j("Ajout.", tool="add_to_cart",
           args={"item_id": "poulet", "quantity": 1, "price": 999}),
        _j("C'est ajouté."),
    ])
    out = h.ask("Ajoute un poulet à 999 FCFA")
    assert out["cart"]["total"] == 12000  # server truth, not model's 999
    assert out["cart"]["total"] != 999


def test_explicit_confirmation_still_required(env):
    h = env([
        _j("Tentative.", tool="create_order", args={}),
        _j("Confirmation requise."),
    ])
    out = h.ask("va y maintenant")
    assert out["order"] is None
    assert not h.svc.create_order_calls


# ============ 7. D1.22 quota still applied before the model ============
def test_quota_still_blocks_before_model(env, monkeypatch):
    monkeypatch.setattr(ag, "svc", PrivacySvc())
    monkeypatch.setattr(tools_mod, "svc", PrivacySvc())
    calls = []
    prov = ScriptedProvider(lambda sp, m: calls.append(1) or _j("ok"))
    for _ in range(quota.MAX_REQUESTS_PER_RESTAURANT):
        quota.check_request("rest-1")
    with pytest.raises(HTTPException) as e:
        _run(ag.process_message(FakeDB(), "rest_demo_chezawa", None, "salut", prov))
    assert e.value.status_code == 429
    assert calls == []


# ============ D1.25 — redaction of the persisted history ============
def test_redaction_regex_units():
    red = ag._redact_contacts
    assert red("joins au 0707070707 merci") == "joins au [TEL] merci"
    assert red("mail : jean.k@exemple.ci ok") == "mail : [EMAIL] ok"
    assert red("C'est 5000 FCFA et 12000 au total") == "C'est 5000 FCFA et 12000 au total"
    assert red("pour le 2026-10-09") == "pour le 2026-10-09"
    assert red("") == ""
    assert red("je confirme") == "je confirme"


def test_persisted_history_redacted_current_turn_keeps_raw(env):
    h = env([
        _j("Client enregistré.",
           tool="set_customer",
           args={"first_name": "Jeanne", "last_name": "KOUASSI",
                 "phone": "0707070707", "email": "jeanne@example.ci"}),
        _j("Vos coordonnées sont enregistrées, KOUASSI Jeanne."),
    ])
    h.ask("Je suis KOUASSI Jeanne au 0707070707, jeanne@example.ci")

    # current turn: the provider saw the raw message (set_customer needs it)
    assert "0707070707" in str(h.turns[0])

    # persisted copy: contacts redacted in both stored messages
    stored = h.db.ai_conversations.docs[0]["messages"]
    flat = str(stored)
    assert "0707070707" not in flat
    assert "jeanne@example.ci" not in flat
    assert "[TEL]" in flat and "[EMAIL]" in flat
    # structured record kept intact for order creation (no storage change)
    cust = h.db.ai_conversations.docs[0]["customer"]
    assert cust["phone"] == "0707070707" and cust["email"] == "jeanne@example.ci"
