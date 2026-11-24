"""V1 — résolution du modèle IA (override > plan > global > env)."""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from models import validate_ai_settings, PlanCreate, PlanUpdate
from services.ai.provider import resolve_ai_settings, effective_ai_settings, get_provider_for_restaurant
from services.ai.gemini_provider import GeminiProvider
from services.ai.bytez_provider import BytezProvider


def test_resolution_plan_wins_over_global_and_env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "env-model")
    resolved = resolve_ai_settings(
        {"plan": "BUSINESS"},
        {"ai": {"provider": "gemini", "model": "plan-model"}},
        {"provider": "gemini", "model": "global-model"},
    )
    assert resolved == {"provider": "gemini", "model": "plan-model", "source": "plan"}


def test_resolution_global_when_plan_has_no_ai(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "env-model")
    resolved = resolve_ai_settings({"plan": "STARTER"}, {}, {"provider": "gemini", "model": "global-model"})
    assert resolved["source"] == "global"
    assert resolved["model"] == "global-model"


def test_resolution_env_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "env-model")
    resolved = resolve_ai_settings({}, {}, {})
    assert resolved == {"provider": "gemini", "model": "env-model", "source": "env"}


def test_resolution_override_wins(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "env-model")
    resolved = resolve_ai_settings(
        {"ai_override": {"provider": "bytez", "model": "openai/gpt-4o"}},
        {"ai": {"provider": "gemini", "model": "plan-model"}},
        {},
    )
    assert resolved["source"] == "override"
    assert resolved["provider"] == "bytez"


def test_invalid_settings_are_ignored(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "env-model")
    resolved = resolve_ai_settings({}, {"ai": {"provider": "inconnu", "model": "x"}}, {})
    assert resolved["source"] == "env"


def test_get_provider_uses_plan_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    provider = get_provider_for_restaurant({}, {"ai": {"provider": "gemini", "model": "gemini-2.5-pro"}}, {})
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-2.5-pro"


def test_get_provider_bytez(monkeypatch):
    monkeypatch.setenv("BYTEZ_API_KEY", "k")
    monkeypatch.setenv("BYTEZ_PROVIDER_KEY", "p")
    provider = get_provider_for_restaurant({}, {"ai": {"provider": "bytez", "model": "openai/gpt-4o"}}, {})
    assert isinstance(provider, BytezProvider)
    assert provider._model == "openai/gpt-4o"


def test_get_provider_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        get_provider_for_restaurant({}, {"ai": {"provider": "gemini", "model": "m"}}, {})
    assert exc.value.status_code == 503


def test_validate_ai_settings():
    assert validate_ai_settings(None) is None
    assert validate_ai_settings({}) is None
    assert validate_ai_settings({"provider": "gemini", "model": "m"}) == {"provider": "gemini", "model": "m"}
    with pytest.raises(ValueError):
        validate_ai_settings({"provider": "inconnu", "model": "m"})
    with pytest.raises(ValueError):
        validate_ai_settings({"provider": "bytez", "model": "sans-slash"})


def test_plan_models_validate_ai():
    plan = PlanCreate(code="TEST", name="Test", price=0, ai={"provider": "gemini", "model": "m"})
    assert plan.ai == {"provider": "gemini", "model": "m"}
    with pytest.raises(ValidationError):
        PlanCreate(code="TEST", name="Test", price=0, ai={"provider": "inconnu", "model": "m"})
    with pytest.raises(ValidationError):
        PlanUpdate(ai={"provider": "bytez", "model": "sans-slash"})


def test_effective_ai_settings_exposes_source(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "env-model")
    assert effective_ai_settings({}, {}, {})["source"] == "env"
