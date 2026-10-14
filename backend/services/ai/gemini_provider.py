"""Gemini implementation of AIProvider using the Google GenAI SDK.

D1.20 robustness patch:
- explicit request timeout: transport timeout (HttpOptions) + asyncio safety net
- bounded generation: max_output_tokens=1024
- structured error mapping (504 timeout, 429 quota, 400 invalid, 503 auth/down,
  502 unexpected) instead of a blanket 502
- client reused per event loop (one Client per loop; rebuilt if the loop
  changes, e.g. per-test asyncio.run, so no cross-loop sharing)
- minimal technical logs: duration, error category/code, token usage when
  present. Never prompts, user messages, menu, customer data or API keys.
"""
import asyncio
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .provider import AIProvider, render_transcript

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 30.0
MAX_OUTPUT_TOKENS = 1024
_GENERIC_MSG = "Le service IA n'a pas pu répondre. Réessayez."


def _timeout_s() -> float:
    """Request timeout in seconds (env AI_TIMEOUT_S, default 30s)."""
    raw = os.environ.get("AI_TIMEOUT_S", "").strip()
    try:
        val = float(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        val = DEFAULT_TIMEOUT_S
    return val if val > 0 else DEFAULT_TIMEOUT_S


# One Client per (event loop, api key). Uvicorn runs a single loop for the
# whole process, so the client is reused across requests. Tests using
# asyncio.run() get a fresh loop -> fresh client, avoiding cross-loop reuse
# of httpx connection pools. Dead loops are dropped when the dict grows
# beyond _MAX_CLIENTS (bounded, test-only scenario).
_MAX_CLIENTS = 8
_clients: Dict[Tuple, genai.Client] = {}


def _get_client(api_key: str) -> genai.Client:
    loop = asyncio.get_running_loop()
    # Key on the loop object itself (not id(loop)): ids of dead loops can be
    # reused by the allocator, which would leak a cross-loop client.
    key = (loop, api_key)
    client = _clients.get(key)
    if client is None:
        if len(_clients) >= _MAX_CLIENTS:
            _clients.clear()
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(_timeout_s() * 1000),
                retry_options=None,  # explicit: no automatic retries (no cost multiplication)
            ),
        )
        _clients[key] = client
    return client


def _http_error_for(exc: BaseException) -> HTTPException:
    """Map an exception to an HTTPException. Never exposes raw SDK messages."""
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
        return HTTPException(status_code=504, detail="Le service IA a mis trop de temps à répondre. Réessayez.")
    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        code = code if isinstance(code, int) else None
        if code in (401, 403):
            # Auth/config problem on our side: report as unavailability, no secret.
            return HTTPException(status_code=503, detail="Service IA momentanément indisponible.")
        if code == 400:
            return HTTPException(status_code=400, detail="Requête invalide pour le service IA.")
        if code == 429:
            return HTTPException(status_code=429, detail="Quota du service IA dépassé. Réessayez plus tard.")
        if code is not None and 500 <= code < 600:
            return HTTPException(status_code=503, detail="Service IA momentanément indisponible.")
        return HTTPException(status_code=502, detail=_GENERIC_MSG)
    if isinstance(exc, httpx.ConnectError):
        return HTTPException(status_code=503, detail="Service IA momentanément indisponible.")
    return HTTPException(status_code=502, detail=_GENERIC_MSG)


def _usage_parts(response) -> Tuple[Optional[int], Optional[int]]:
    """Token counts from usage_metadata when present, else (None, None).

    Indicative usage only — not an exact billing figure (pricing rules apply
    separately). Absent metadata must never raise.
    """
    try:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return None, None
        tin = getattr(usage, "prompt_token_count", None)
        tout = getattr(usage, "candidates_token_count", None)
        return (tin if isinstance(tin, int) else None, tout if isinstance(tout, int) else None)
    except Exception:
        return None, None


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, system_prompt: str, messages: List[Dict]) -> str:
        transcript = render_transcript(messages)
        user_text = (
            "Voici la conversation jusqu'à présent. Réponds UNIQUEMENT avec l'objet JSON demandé "
            "(aucun texte hors JSON).\n\n" + transcript + "\n\nASSISTANT (JSON):"
        )
        timeout_s = _timeout_s()
        client = _get_client(self.api_key)
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        t0 = time.perf_counter()

        def _ms() -> int:
            return int((time.perf_counter() - t0) * 1000)

        try:
            # asyncio.wait_for cancels the in-flight coroutine on expiry; with
            # retries disabled this is a single request, never a second one.
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model,
                    contents=user_text,
                    config=config,
                ),
                timeout=timeout_s + 1.0,
            )
            result = response.text
        except (asyncio.TimeoutError, httpx.TimeoutException) as e:
            he = _http_error_for(e)
            logger.warning("gemini_error category=timeout http=%d ms=%d", he.status_code, _ms())
            raise he from None
        except genai_errors.APIError as e:
            he = _http_error_for(e)
            code = getattr(e, "code", None)
            logger.warning(
                "gemini_error category=api http=%d sdk_code=%s ms=%d",
                he.status_code, code if isinstance(code, int) else "unknown", _ms(),
            )
            raise he from None
        except httpx.ConnectError as e:
            he = _http_error_for(e)
            logger.warning("gemini_error category=network http=%d ms=%d", he.status_code, _ms())
            raise he from None
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("gemini_error category=unexpected type=%s http=502 ms=%d", type(e).__name__, _ms())
            raise HTTPException(status_code=502, detail=_GENERIC_MSG) from None

        tin, tout = _usage_parts(response)
        logger.info("gemini_call ms=%d model=%s tokens_in=%s tokens_out=%s", _ms(), self.model, tin, tout)
        return result if isinstance(result, str) else str(result)


def get_default_provider() -> AIProvider:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if not key:
        raise HTTPException(status_code=503, detail="Service IA non configuré")
    return GeminiProvider(key, model)
