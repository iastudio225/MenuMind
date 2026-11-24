"""AI provider abstraction — swappable backend so the agent is not coupled to Gemini."""
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from fastapi import HTTPException


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, messages: List[Dict]) -> str:
        """Return the model's raw text completion for the given system prompt + transcript."""
        raise NotImplementedError


def render_transcript(messages: List[Dict]) -> str:
    lines = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "user":
            lines.append(f"CLIENT: {content}")
        elif role == "assistant":
            lines.append(f"ASSISTANT: {content}")
        elif role == "tool":
            lines.append(f"[RÉSULTAT OUTIL {m.get('name','')}]: {content}")
    return "\n".join(lines)


class ScriptedProvider(AIProvider):
    """Deterministic provider for tests. `handler(system_prompt, messages) -> str`."""
    def __init__(self, handler):
        self._handler = handler

    async def generate(self, system_prompt: str, messages: List[Dict]) -> str:
        res = self._handler(system_prompt, messages)
        return res


def get_configured_provider() -> AIProvider:
    """Select exactly one provider from configuration (no automatic fallback).

    ``AI_GATEWAY=bytez`` (or legacy ``AI_PROVIDER=bytez``) -> BytezProvider.
    Anything else -> the historical direct Gemini provider.
    """
    gateway = (os.environ.get("AI_GATEWAY", "") or os.environ.get("AI_PROVIDER", "gemini")).strip().lower()
    if gateway == "bytez":
        from .bytez_provider import provider_from_env
        return provider_from_env()
    from .gemini_provider import get_default_provider
    return get_default_provider()


def _env_ai_settings() -> Optional[dict]:
    gateway = (os.environ.get("AI_GATEWAY", "") or os.environ.get("AI_PROVIDER", "gemini")).strip().lower()
    if gateway == "bytez":
        model = (os.environ.get("AI_MODEL") or "").strip()
        return {"provider": "bytez", "model": model} if model else None
    model = (os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
    return {"provider": "gemini", "model": model} if model else None


def _valid_ai_settings(settings) -> Optional[dict]:
    if not isinstance(settings, dict):
        return None
    provider = str(settings.get("provider") or "").strip().lower()
    model = str(settings.get("model") or "").strip()
    if provider not in ("gemini", "bytez") or not model:
        return None
    if provider == "bytez" and "/" not in model:
        return None
    return {"provider": provider, "model": model}


def resolve_ai_settings(restaurant=None, plan=None, platform=None) -> Optional[dict]:
    """Resolution order: override restaurant > plan > global > env.

    V1 stores the model on the plan; the restaurant override is reserved for a
    later version but already supported here without changing the contract.
    """
    restaurant = restaurant or {}
    plan = plan or {}
    platform = platform or {}
    candidates = [
        (restaurant.get("ai_override"), "override"),
        (plan.get("ai"), "plan"),
        (platform.get("ai") if isinstance(platform.get("ai"), dict) else platform, "global"),
        (_env_ai_settings(), "env"),
    ]
    for settings, source in candidates:
        valid = _valid_ai_settings(settings)
        if valid:
            return {**valid, "source": source}
    return None


def effective_ai_settings(restaurant=None, plan=None, platform=None) -> Optional[dict]:
    return resolve_ai_settings(restaurant, plan, platform)


def get_provider_for_restaurant(restaurant=None, plan=None, platform=None) -> AIProvider:
    """Build the provider from the resolved settings, without touching tripwires."""
    settings = resolve_ai_settings(restaurant, plan, platform)
    if not settings:
        return get_configured_provider()
    provider = settings["provider"]
    model = settings["model"]
    if provider == "bytez":
        from .bytez_provider import BytezProvider
        api_key = (os.environ.get("BYTEZ_API_KEY") or "").strip()
        provider_key = (os.environ.get("BYTEZ_PROVIDER_KEY") or "").strip()
        if not api_key or not provider_key:
            raise HTTPException(status_code=503, detail="Service IA non configuré (clés Bytez manquantes)")
        return BytezProvider(api_key=api_key, provider_key=provider_key, model=model)
    from .gemini_provider import GeminiProvider
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="Service IA non configuré")
    return GeminiProvider(key, model)
