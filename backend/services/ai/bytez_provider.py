"""Bytez gateway implementation of AIProvider (D1.10).

Routes MenuMind's provider-independent ``AIProvider`` contract through the
Bytez unified API. The business pipeline (``_parse_action`` / tools / order
engine) only ever sees the returned ``str`` and is untouched by this adapter.

Configuration is read from the environment (never hardcoded, never logged):

- ``BYTEZ_API_KEY``: Bytez gateway key (``Authorization`` header).
- ``BYTEZ_PROVIDER_KEY``: underlying provider key (``provider-key`` header,
  e.g. the Gemini key for ``google/...`` models — required for closed-source).
- ``AI_MODEL``: ``provider/model`` reference, e.g. ``google/gemini-2.5-flash``.
- ``AI_TEMPERATURE`` / ``AI_MAX_TOKENS``: optional tuning, omitted when unset.
- ``AI_TIMEOUT_S``: HTTP timeout in seconds (default 60).
"""
import json
import logging
import os
from typing import List, Dict, Optional

import httpx
from fastapi import HTTPException

from .provider import AIProvider, render_transcript

logger = logging.getLogger(__name__)

BYTEZ_BASE_URL = "https://api.bytez.com"
DEFAULT_TIMEOUT_S = 60


class BytezProvider(AIProvider):
    """AIProvider backed by the Bytez unified API (universal closed-source route).

    Uses a single coherent route per configured model:
    ``POST {base}/models/v2/{provider}/{model}`` with
    ``{"messages": [{"role": "system", ...}, {"role": "user", ...}], ...}``
    and extracts the standardized ``output`` field as plain ``str``.
    """

    def __init__(
        self,
        api_key: str,
        provider_key: str,
        model: str,
        base_url: str = BYTEZ_BASE_URL,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        if not api_key:
            raise ValueError("BYTEZ_API_KEY manquante")
        if not provider_key:
            raise ValueError("BYTEZ_PROVIDER_KEY manquante (clé du provider sous-jacent requise)")
        if not model or "/" not in model:
            raise ValueError("AI_MODEL invalide (format attendu: provider/modèle, ex. google/gemini-2.5-flash)")
        self._api_key = api_key
        self._provider_key = provider_key
        self._model = model
        self._base_url = (base_url or BYTEZ_BASE_URL).rstrip("/")
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_s = timeout_s
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    def build_payload(self, system_prompt: str, messages: List[Dict]) -> dict:
        """Build the exact Bytez request body (exposed for unit tests)."""
        transcript = render_transcript(messages)
        user_text = (
            "Voici la conversation jusqu'à présent. Réponds UNIQUEMENT avec l'objet JSON demandé "
            "(aucun texte hors JSON).\n\n" + transcript + "\n\nASSISTANT (JSON):"
        )
        payload: dict = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "stream": False,
        }
        params: dict = {}
        if self._temperature is not None:
            params["temperature"] = self._temperature
        if self._max_tokens is not None:
            params["max_length"] = self._max_tokens
        if params:
            payload["params"] = params
        return payload

    def _path(self) -> str:
        provider, _, name = self._model.partition("/")
        return f"/models/v2/{provider}/{name}"

    async def generate(self, system_prompt: str, messages: List[Dict]) -> str:
        payload = self.build_payload(system_prompt, messages)
        headers = {
            "Authorization": self._api_key,
            "provider-key": self._provider_key,
            "Content-Type": "application/json",
        }
        url = self._base_url + self._path()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as e:
            # Network/timeout: never leak headers or keys, only the error type.
            logger.error("Erreur réseau Bytez: %s (model=%s)", type(e).__name__, self._model)
            raise HTTPException(status_code=502, detail="Le service IA n'a pas pu répondre. Réessayez.")
        return self._extract(response)

    def _extract(self, response: httpx.Response) -> str:
        status = response.status_code
        if status == 401:
            logger.error("Bytez 401 (model=%s): clé Bytez/provider absente ou invalide", self._model)
            raise HTTPException(status_code=401, detail="Clé IA invalide. Vérifiez la configuration.")
        if status == 402:
            logger.error("Bytez 402 (model=%s): crédits insuffisants", self._model)
            raise HTTPException(status_code=402, detail="Crédits IA insuffisants.")
        if status == 429:
            detail = _safe_detail(response)
            logger.error("Bytez 429 (model=%s): %s", self._model, detail)
            # D1.25: never echo raw provider bodies to the client — the detail
            # (even truncated) can in theory echo prompt content.
            raise HTTPException(status_code=429, detail="Quota IA dépassé. Réessayez plus tard.")
        if status != 200:
            logger.error("Bytez HTTP %s (model=%s): %s", status, self._model, _safe_detail(response))
            raise HTTPException(status_code=502, detail="Le service IA n'a pas pu répondre. Réessayez.")
        try:
            body = response.json()
        except Exception:
            logger.error("Bytez: réponse non-JSON (model=%s)", self._model)
            raise HTTPException(status_code=502, detail="Le service IA n'a pas pu répondre. Réessayez.")
        err = body.get("error") if isinstance(body, dict) else None
        if err:
            logger.error("Bytez error (model=%s): %s", self._model, str(err)[:120])
            raise HTTPException(status_code=502, detail="Le service IA n'a pas pu répondre. Réessayez.")
        output = body.get("output") if isinstance(body, dict) else None
        if output is None:
            logger.error("Bytez: champ 'output' manquant (model=%s)", self._model)
            raise HTTPException(status_code=502, detail="Le service IA n'a pas pu répondre. Réessayez.")
        return output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)


def _safe_detail(response: httpx.Response) -> str:
    """Provider error code only — never a raw body (D1.25: a raw excerpt could
    echo prompt or personal data; logs keep a controlled 120-char slice)."""
    try:
        body = response.json()
    except Exception:
        return "n/a"
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            return err["message"][:120]
        if isinstance(err, str):
            return err[:120]
    return "n/a"


def provider_from_env() -> BytezProvider:
    """Build a BytezProvider from environment configuration (no hardcoded model)."""
    api_key = os.environ.get("BYTEZ_API_KEY", "").strip()
    provider_key = os.environ.get("BYTEZ_PROVIDER_KEY", "").strip()
    model = os.environ.get("AI_MODEL", "").strip()
    if not api_key or not provider_key:
        raise HTTPException(status_code=503, detail="Service IA non configuré (BYTEZ_API_KEY / BYTEZ_PROVIDER_KEY manquants)")
    if not model:
        raise HTTPException(status_code=503, detail="Service IA non configuré (AI_MODEL manquant)")
    temperature = _optional_float(os.environ.get("AI_TEMPERATURE", "").strip())
    max_tokens = _optional_int(os.environ.get("AI_MAX_TOKENS", "").strip())
    timeout_s = _optional_int(os.environ.get("AI_TIMEOUT_S", "").strip()) or DEFAULT_TIMEOUT_S
    try:
        return BytezProvider(
            api_key=api_key, provider_key=provider_key, model=model,
            temperature=temperature, max_tokens=max_tokens, timeout_s=timeout_s,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"Service IA mal configuré ({e})")


def _optional_float(value: str) -> Optional[float]:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _optional_int(value: str) -> Optional[int]:
    try:
        return int(value) if value else None
    except ValueError:
        return None
