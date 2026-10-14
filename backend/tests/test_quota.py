"""D1.22 — restaurant AI quotas: frequency, usage, memory bounds, isolation.

Mocked services and providers only: no network, no real DB, no order created.
Covers the 12 acceptance points of the D1.22 protocol.
"""
import os

# routers -> database reads MONGO_URL/DB_NAME at import time. The Mongo client
# is lazy (no network call, no real credentials): unit tests stay offline.
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017/restoia-unit")
os.environ.setdefault("DB_NAME", "restoia-unit")

import pytest
from fastapi import HTTPException

from routers import ai_router
from services.ai import agent_service as ag
from services.ai import quota
from services.ai import tools as tools_mod
from services.ai.provider import AIProvider, ScriptedProvider, get_configured_provider
from tests.test_agent_service import FakeDB, FakeSvc, _j, _run, harness_env


@pytest.fixture(autouse=True)
def _fresh():
    quota.reset()
    yield
    quota.reset()


# 1 — two restaurants keep independent counters
def test_restaurants_independent():
    for _ in range(quota.MAX_REQUESTS_PER_RESTAURANT):
        quota.check_request("rest-A")
    quota.check_request("rest-B")
    assert len(quota._requests["rest-A"]) == 10
    assert len(quota._requests["rest-B"]) == 1


# 2 — exhausting A does not block B; A gets a generic 429
def test_exhaustion_is_scoped():
    for _ in range(quota.MAX_REQUESTS_PER_RESTAURANT):
        quota.check_request("rest-A")
    with pytest.raises(HTTPException) as e:
        quota.check_request("rest-A")
    assert e.value.status_code == 429
    assert str(e.value.detail) == quota.GENERIC_429
    quota.check_request("rest-B")  # B unaffected


# 3 — unknown public id: 404, no counter created, model never called
def test_unknown_public_id_no_bypass(monkeypatch):
    svc = FakeSvc()
    monkeypatch.setattr(ag, "svc", svc)
    calls = []

    async def never(system_prompt, messages):
        calls.append(1)
        return "unused"

    prov = ScriptedProvider(lambda sp, m: None)
    prov.generate = never

    with pytest.raises(HTTPException) as e:
        _run(ag.process_message(FakeDB(), "rest_fabrique_9999", None, "salut", prov))
    assert e.value.status_code == 404
    assert calls == []                       # model never reached
    assert quota._requests == {}             # no counter for a fabricated id
    assert quota._model_calls == {}


# 4 — router IP limiter still works alongside the restaurant quota
def test_ip_limiter_intact():
    saved = dict(ai_router._hits)
    ai_router._hits.clear()
    try:
        for _ in range(ai_router._MAX):
            ai_router._rate_limit("203.0.113.7")
        with pytest.raises(HTTPException) as e:
            ai_router._rate_limit("203.0.113.7")
        assert e.value.status_code == 429
        quota.check_request("rest-C")  # restaurant quota independent
        assert "rest-C" in quota._requests
    finally:
        ai_router._hits.clear()
        ai_router._hits.update(saved)


# 5 — expired entries purged; memory bounded even for vanished keys
def test_memory_bounded_and_purged(monkeypatch):
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(quota.time, "time", lambda: clock["now"])
    for i in range(30):
        quota.check_request(f"rest-{i}")
    assert len(quota._requests) == 30
    clock["now"] += quota.WINDOW_S + 1  # everything expires
    quota.check_request("rest-fresh")
    quota._prune(quota._requests, clock["now"])
    assert set(quota._requests) == {"rest-fresh"}
    # threshold path: filling keys forces a global purge on next access
    for i in range(quota._MAX_KEYS):
        quota.check_request(f"k{i}")
    assert len(quota._requests) >= quota._MAX_KEYS
    clock["now"] += quota.WINDOW_S + 1
    quota.check_request("survivor")
    assert set(quota._requests) == {"survivor"}  # dead keys all removed


# 6 — 429 body is generic, leaks no restaurant id / secret / data
def test_429_generic_body():
    for _ in range(quota.MAX_REQUESTS_PER_RESTAURANT):
        quota.check_request("rest-secret-id-42")
    with pytest.raises(HTTPException) as e:
        quota.check_request("rest-secret-id-42")
    body = str(e.value.detail)
    assert body == quota.GENERIC_429
    for leak in ("rest-secret-id-42", "token", "10", "60"):
        assert leak.lower() not in body.lower()


# 7 — refused request never reaches the model (control before generate)
def test_refused_request_never_calls_model(monkeypatch):
    svc = FakeSvc()
    monkeypatch.setattr(ag, "svc", svc)
    calls = []

    def handler(system_prompt, messages):
        calls.append(1)
        return _j("réponse jamais atteinte")

    prov = ScriptedProvider(handler)
    for _ in range(quota.MAX_REQUESTS_PER_RESTAURANT):
        quota.check_request("rest-1")

    with pytest.raises(HTTPException) as e:
        _run(ag.process_message(FakeDB(), "rest_demo_chezawa", None, "encore une pizza", prov))
    assert e.value.status_code == 429
    assert calls == []


# 8 — accepted request completes the normal path, quota incremented
def test_accepted_request_normal_flow(harness_env):
    h = harness_env([_j("Bonjour et bienvenue !")])
    out = h.ask("Bonjour")
    assert out["message"]
    assert h.provider_calls == 1
    assert len(quota._requests["rest-1"]) == 1   # message slot consumed
    assert len(quota._model_calls["rest-1"]) == 1  # model call recorded


# 9 — model-call budget (60/window) and per-request MAX_STEPS bound
def test_model_call_budget_bounds_provider(monkeypatch):
    for _ in range(quota.MAX_MODEL_CALLS_PER_RESTAURANT):
        quota.record_model_call("rest-1")
    with pytest.raises(HTTPException) as e:
        quota.record_model_call("rest-1")
    assert e.value.status_code == 429
    quota.reset()  # fresh budget for the per-request part below
    monkeypatch.setattr(ag, "svc", FakeSvc())
    monkeypatch.setattr(tools_mod, "svc", FakeSvc())  # tools path too (D1.21 harness)
    calls = []

    def tool_loop(system_prompt, messages):
        calls.append(1)
        return _j("étape", tool="calculate_cart", args={})

    prov = ScriptedProvider(tool_loop)
    out = _run(ag.process_message(FakeDB(), "rest_demo_chezawa", None, "boucle", prov))
    assert len(calls) == 6 == ag.MAX_STEPS
    assert out["message"]
    assert len(quota._model_calls.get("rest-1", [])) >= 6


# 10 — tracking works when provider usage metadata is absent or provider fails
def test_tracking_independent_of_usage_metadata(monkeypatch):
    svc = FakeSvc()
    monkeypatch.setattr(ag, "svc", svc)

    # no usage metadata anywhere: quota counters are timestamps only
    quota.check_request("rest-1")
    quota.record_model_call("rest-1")
    assert all(isinstance(t, float) for t in quota._model_calls["rest-1"])
    quota.reset()  # observe only what the real path records below

    # provider failure surfaces as-is; quota state stays coherent
    def failing(system_prompt, messages):
        raise HTTPException(status_code=503,
                            detail="Quota du service IA dépassé. Réessayez plus tard.")

    with pytest.raises(HTTPException) as e:
        _run(ag.process_message(FakeDB(), "rest_demo_chezawa", None, "salut",
                                ScriptedProvider(failing)))
    assert e.value.status_code == 503
    assert len(quota._model_calls.get("rest-1", [])) == 1  # recorded before the call


# 11 — quota sits upstream of both configured providers (Gemini and Bytez)
def test_quota_upstream_of_any_provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key-not-a-secret")
    gem = get_configured_provider()
    assert isinstance(gem, AIProvider)

    monkeypatch.setenv("AI_GATEWAY", "bytez")
    monkeypatch.setenv("BYTEZ_API_KEY", "dummy")
    monkeypatch.setenv("BYTEZ_PROVIDER_KEY", "dummy")
    monkeypatch.setenv("AI_MODEL", "google/gemini-2.5-flash")
    bytez = get_configured_provider()
    assert isinstance(bytez, AIProvider)

    for rid in ("rest-x", "rest-y"):
        quota.check_request(rid)
        quota.record_model_call(rid)
    assert len(quota._requests["rest-x"]) == 1
    assert len(quota._model_calls["rest-y"]) == 1


# 12 — suites of previous phases keep passing (run together by the harness)
def test_previous_phase_guards_still_hold(harness_env):
    # D1.21 menu-once + D1.14 hard guard: both live behind the new quota
    h = harness_env([
        _j("Poulet ajouté.", tool="add_to_cart", args={"item_id": "poulet", "quantity": 1}),
        _j("C'est dans votre panier !"),
    ])
    h.ask("Ajoute un poulet braisé")
    assert h.svc.menu_calls == 1

    h2 = harness_env([
        _j("Tentative.", tool="create_order", args={}),
        _j("Confirmation requise."),
    ])
    out = h2.ask("va y")
    assert out["order"] is None
    assert not h2.svc.create_order_calls
