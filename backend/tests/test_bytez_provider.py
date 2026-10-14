"""
RestoIA D1.10 — BytezProvider adapter unit tests (no network, no DB).

Covers: AIProvider contract, Bytez payload shape, output extraction,
HTTP error mapping (401/402/429/5xx/network), and AI_GATEWAY/AI_MODEL
factory selection. All HTTP is mocked via httpx.MockTransport.
"""
import inspect
import json

import httpx
import pytest
from fastapi import HTTPException

from services.ai.bytez_provider import BytezProvider, provider_from_env
from services.ai.provider import AIProvider, get_configured_provider
from services.ai.gemini_provider import GeminiProvider


def _provider(handler, **kw):
    kw.setdefault("api_key", "TEST-BYTEZ-KEY")
    kw.setdefault("provider_key", "TEST-PROVIDER-KEY")
    kw.setdefault("model", "google/gemini-2.5-flash")
    kw.setdefault("transport", httpx.MockTransport(handler))
    return BytezProvider(**kw)


def _ok(body):
    def handler(request):
        return httpx.Response(200, json=body)
    return handler


MSGS = [
    {"role": "user", "content": "Je veux 2 poulets"},
    {"role": "assistant", "content": "Avec plaisir"},
    {"role": "tool", "name": "calculate_cart", "content": '{"total": 11000}'},
]


# =============== 5. AIProvider contract ===============
class TestContract:
    def test_is_ai_provider(self):
        assert issubclass(BytezProvider, AIProvider)

    def test_generate_signature(self):
        sig = inspect.signature(BytezProvider.generate)
        assert list(sig.parameters) == ["self", "system_prompt", "messages"]
        assert inspect.iscoroutinefunction(BytezProvider.generate)

    def test_model_not_hardcoded_requires_config(self):
        with pytest.raises(ValueError):
            BytezProvider(api_key="k", provider_key="p", model="")
        with pytest.raises(ValueError):
            BytezProvider(api_key="k", provider_key="p", model="no-slash-here")


# =============== 1. Payload ===============
class TestPayload:
    def test_system_and_transcript_mapping(self):
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content.decode())
            seen["path"] = request.url.path
            seen["auth"] = request.headers.get("authorization")
            seen["pkey"] = request.headers.get("provider-key")
            return httpx.Response(200, json={"error": None, "output": "ok"})

        p = _provider(handler)
        out = _run(p.generate("SYS-PROMPT", MSGS))
        assert out == "ok"
        body = seen["body"]
        assert body["messages"][0] == {"role": "system", "content": "SYS-PROMPT"}
        user = body["messages"][1]
        assert user["role"] == "user"
        assert "CLIENT: Je veux 2 poulets" in user["content"]
        assert "ASSISTANT: Avec plaisir" in user["content"]
        assert "RÉSULTAT OUTIL calculate_cart" in user["content"]
        assert body["stream"] is False
        assert "params" not in body  # provider defaults when unset
        assert seen["path"] == "/models/v2/google/gemini-2.5-flash"
        assert seen["auth"] == "TEST-BYTEZ-KEY"
        assert seen["pkey"] == "TEST-PROVIDER-KEY"

    def test_tuning_params_forwarded(self):
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(200, json={"error": None, "output": "ok"})

        p = _provider(handler, temperature=0.2, max_tokens=512)
        _run(p.generate("S", [{"role": "user", "content": "hi"}]))
        assert seen["body"]["params"] == {"temperature": 0.2, "max_length": 512}

    def test_other_provider_path(self):
        seen = {}

        def handler(request):
            seen["path"] = request.url.path
            return httpx.Response(200, json={"error": None, "output": "ok"})

        p = _provider(handler, model="openai/gpt-4o")
        _run(p.generate("S", []))
        assert seen["path"] == "/models/v2/openai/gpt-4o"


# =============== 2. Output extraction ===============
class TestOutput:
    def test_string_output(self):
        p = _provider(_ok({"error": None, "output": "Bonjour"}))
        assert _run(p.generate("S", [])) == "Bonjour"

    def test_non_string_output_serialized(self):
        p = _provider(_ok({"error": None, "output": {"a": 1}}))
        assert _run(p.generate("S", [])) == '{"a": 1}'

    def test_error_field_raises(self):
        p = _provider(_ok({"error": "boom", "output": ""}))
        with pytest.raises(HTTPException) as e:
            _run(p.generate("S", []))
        assert e.value.status_code == 502

    def test_missing_output_raises(self):
        p = _provider(_ok({"error": None}))
        with pytest.raises(HTTPException) as e:
            _run(p.generate("S", []))
        assert e.value.status_code == 502

    def test_non_json_raises(self):
        def handler(request):
            return httpx.Response(200, text="not json")
        p = _provider(handler)
        with pytest.raises(HTTPException) as e:
            _run(p.generate("S", []))
        assert e.value.status_code == 502


# =============== 3. Error mapping (no real network) ===============
class TestErrors:
    @pytest.mark.parametrize("status,expected", [(401, 401), (402, 402), (429, 429), (500, 502), (503, 502)])
    def test_status_mapping(self, status, expected):
        def handler(request):
            return httpx.Response(status, json={"error": "x"})
        p = _provider(handler)
        with pytest.raises(HTTPException) as e:
            _run(p.generate("S", []))
        assert e.value.status_code == expected

    def test_network_failure_is_502(self):
        def handler(request):
            raise httpx.ConnectError("down")
        p = _provider(handler)
        with pytest.raises(HTTPException) as e:
            _run(p.generate("S", []))
        assert e.value.status_code == 502


# =============== 4. Configuration / factory ===============
class TestFactory:
    def test_bytez_selected(self, monkeypatch):
        monkeypatch.setenv("AI_GATEWAY", "bytez")
        monkeypatch.setenv("AI_MODEL", "google/gemini-2.5-flash")
        monkeypatch.setenv("BYTEZ_API_KEY", "k")
        monkeypatch.setenv("BYTEZ_PROVIDER_KEY", "p")
        p = get_configured_provider()
        assert isinstance(p, BytezProvider)
        assert p.model == "google/gemini-2.5-flash"

    def test_legacy_ai_provider_var(self, monkeypatch):
        monkeypatch.delenv("AI_GATEWAY", raising=False)
        monkeypatch.setenv("AI_PROVIDER", "bytez")
        monkeypatch.setenv("AI_MODEL", "openai/gpt-4o")
        monkeypatch.setenv("BYTEZ_API_KEY", "k")
        monkeypatch.setenv("BYTEZ_PROVIDER_KEY", "p")
        p = get_configured_provider()
        assert isinstance(p, BytezProvider) and p.model == "openai/gpt-4o"

    def test_missing_keys_503(self, monkeypatch):
        monkeypatch.setenv("AI_GATEWAY", "bytez")
        monkeypatch.setenv("AI_MODEL", "google/gemini-2.5-flash")
        monkeypatch.delenv("BYTEZ_API_KEY", raising=False)
        monkeypatch.delenv("BYTEZ_PROVIDER_KEY", raising=False)
        with pytest.raises(HTTPException) as e:
            get_configured_provider()
        assert e.value.status_code == 503

    def test_missing_model_503(self, monkeypatch):
        monkeypatch.setenv("AI_GATEWAY", "bytez")
        monkeypatch.delenv("AI_MODEL", raising=False)
        monkeypatch.setenv("BYTEZ_API_KEY", "k")
        monkeypatch.setenv("BYTEZ_PROVIDER_KEY", "p")
        with pytest.raises(HTTPException) as e:
            get_configured_provider()
        assert e.value.status_code == 503

    def test_default_is_gemini_no_fallback(self, monkeypatch):
        # No gateway configured -> historical Gemini path (proves selection is
        # explicit, not a silent Bytez->Gemini fallback inside the adapter).
        monkeypatch.delenv("AI_GATEWAY", raising=False)
        monkeypatch.setenv("AI_PROVIDER", "gemini")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(HTTPException) as e:
            get_configured_provider()
        assert e.value.status_code == 503  # from Gemini factory: no key, no network


# =============== D1.25 — controlled error details ===============
class TestSafeDetailD125:
    def test_429_client_detail_is_generic_no_body_echo(self):
        def handler(request):
            return httpx.Response(429, json={"error": "x",
                                             "echo": "SECRET-PROMPT-EXCERPT"})
        p = _provider(handler)
        with pytest.raises(HTTPException) as e:
            _run(p.generate("S", []))
        assert e.value.status_code == 429
        assert e.value.detail == "Quota IA dépassé. Réessayez plus tard."
        assert "SECRET-PROMPT-EXCERPT" not in str(e.value.detail)

    def test_429_log_never_contains_raw_body(self, caplog):
        def handler(request):
            return httpx.Response(429, json={"error": {"message": "rate limited"},
                                             "raw": "RAW-BODY-WITH-PROMPT"})
        p = _provider(handler)
        with caplog.at_level("ERROR"):
            with pytest.raises(HTTPException):
                _run(p.generate("S", []))
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "Bytez 429" in joined
        assert "RAW-BODY-WITH-PROMPT" not in joined  # non-error fields never logged
        assert "rate limited" in joined              # controlled error.message

    def test_safe_detail_never_returns_raw_text(self):
        from services.ai.bytez_provider import _safe_detail
        raw = httpx.Response(500, text="SECRET-RAW-TEXT")
        assert _safe_detail(raw) == "n/a"
        echo = httpx.Response(500, json={"echo": "SECRET-RAW-TEXT"})
        assert _safe_detail(echo) == "n/a"
        ok = httpx.Response(500, json={"error": {"message": "quota"}})
        assert _safe_detail(ok) == "quota"


def _run(coro):
    import asyncio
    return asyncio.run(coro)
