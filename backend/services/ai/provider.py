"""AI provider abstraction — swappable backend so the agent is not coupled to Gemini."""
import os
from abc import ABC, abstractmethod
from typing import List, Dict


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
