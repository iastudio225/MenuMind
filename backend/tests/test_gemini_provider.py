"""
RestoIA D1.20 — GeminiProvider robustness unit tests (mocked, no network, no DB).

Covers: AIProvider contract, generation config (timeout + max_output_tokens),
structured error mapping (timeout 504, quota 429, invalid 400, auth 503,
provider down 503, unexpected 502), controlled timeout without a second
request, absent usage metadata, per-event-loop client lifecycle, no
automatic retry, and log hygiene (no prompt / PII / API key).
"""
import asyncio
import inspect
import logging

import httpx
import pytest
from fastapi import HTTPException
from google.genai import errors as genai_errors

from services.ai import gemini_provider as gp
from services.ai.gemini_provider import (
    MAX_OUTPUT_TOKENS,
    GeminiProvider,
    get_default_provider,
)
from services.ai.provider import AIProvider, get_configured_provider


def _run(coro):
    return asyncio.run(coro)


class _FakeUsage:
    def __init__(self, tin, tout):
        self.prompt_token_count = tin
        self.candidates_token_count = tout


class _FakeResponse:
    def __init__(self, text='{"message": "ok"}', usage="unset"):
        self.text = text
        if usage != "unset":
            self.usage_metadata = usage


class _FakeModels:
    def __init__(self, text='{"message": "ok"}'):
        self.calls = []
        self.queue = []
        self.text = text

    async def generate_content(self, **kw):
        self.calls.append(kw)
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return _FakeResponse(text=self.text)


class _FakeAio:
    def __init__(self, models):
        self.models = models


class _FakeClient:
    def __init__(self, models):
        self.aio = _FakeAio(models)


@pytest.fixture
def fake(monkeypatch):
    """Replace the client factory: no network, calls captured."""
    models = _FakeModels()
    client = _FakeClient(models)
    monkeypatch.setattr(gp, "_get_client", lambda api_key: client)
    return models


PROMPT = "SECRET-PROMPT-SYSTEM avec telephone 0707070707 et email client@exemple.ci"
MSGS = [
    {"role": "user", "content": "PII-USER tel 0707070707 nom Jean Kouassi"},
    {"role": "assistant", "content": "Bonjour !"},
]


# =============== 9. AIProvider contract ===============
class TestContract:
    def test_is_ai_provider(self):
        assert issubclass(GeminiProvider, AIProvider)

    def test_generate_signature(self):
        sig = inspect.signature(GeminiProvider.generate)
        assert list(sig.parameters) == ["self", "system_prompt", "messages"]
        assert inspect.iscoroutinefunction(GeminiProvider.generate)

    def test_returns_str(self, fake):
        out = _run(GeminiProvider("k", "m").generate(PROMPT, MSGS))
        assert isinstance(out, str)
        assert out == '{"message": "ok"}'


# =============== 1 & 2. Config sent to the SDK ===============
class TestConfig:
    def test_config_has_max_output_tokens_and_system_instruction(self, fake):
        _run(GeminiProvider("k", "gemini-2.5-flash").generate(PROMPT, MSGS))
        call = fake.calls[0]
        cfg = call["config"]
        assert cfg.max_output_tokens == MAX_OUTPUT_TOKENS == 1024
        assert cfg.system_instruction is not None
        sys_text = cfg.system_instruction
        if not isinstance(sys_text, str):
            sys_text = "".join(
                getattr(p, "text", "") or "" for p in (getattr(sys_text, "parts", None) or [])
            )
        assert "SECRET-PROMPT-SYSTEM" in sys_text
        assert call["model"] == "gemini-2.5-flash"

    def test_client_transport_timeout_is_30s(self, monkeypatch):
        monkeypatch.setattr(gp, "_clients", {})
        monkeypatch.delenv("AI_TIMEOUT_S", raising=False)
        _run(_check_timeout())

    def test_timeout_env_override_and_invalid(self, monkeypatch):
        monkeypatch.setenv("AI_TIMEOUT_S", "5")
        assert gp._timeout_s() == 5.0
        monkeypatch.setenv("AI_TIMEOUT_S", "not-a-number")
        assert gp._timeout_s() == gp.DEFAULT_TIMEOUT_S
        monkeypatch.setenv("AI_TIMEOUT_S", "-3")
        assert gp._timeout_s() == gp.DEFAULT_TIMEOUT_S


async def _check_timeout():
    client = gp._get_client("dummy-key-not-real")
    http_opts = client._api_client._http_options
    assert http_opts.timeout == 30_000  # milliseconds, per HttpOptions spec
    assert http_opts.retry_options is None  # no automatic retries


# =============== 3. Error mapping ===============
@pytest.mark.parametrize(
    "exc,expected",
    [
        (genai_errors.ClientError(429, {"error": {"message": "quota"}}), 429),
        (genai_errors.ClientError(401, {"error": {"message": "bad key"}}), 503),
        (genai_errors.ClientError(403, {"error": {"message": "forbidden"}}), 503),
        (genai_errors.ClientError(400, {"error": {"message": "invalid"}}), 400),
        (genai_errors.ServerError(503, {"error": {"message": "down"}}), 503),
        (genai_errors.ServerError(500, {"error": {"message": "boom"}}), 503),
        (httpx.TimeoutException("read timeout"), 504),
        (asyncio.TimeoutError(), 504),
        (httpx.ConnectError("refused"), 503),
        (RuntimeError("unexpected"), 502),
    ],
)
def test_error_mapping(fake, exc, expected):
    fake.queue.append(exc)
    with pytest.raises(HTTPException) as e:
        _run(GeminiProvider("k", "m").generate("S", MSGS))
    assert e.value.status_code == expected


def test_raw_sdk_message_never_exposed(fake):
    fake.queue.append(genai_errors.ClientError(429, {"error": {"message": "SECRET-GOOGLE-MSG"}}))
    with pytest.raises(HTTPException) as e:
        _run(GeminiProvider("k", "m").generate("S", MSGS))
    assert "SECRET-GOOGLE-MSG" not in str(e.value.detail)


# =============== 4. Controlled timeout, no second request ===============
class _SlowModels:
    def __init__(self):
        self.calls = []

    async def generate_content(self, **kw):
        self.calls.append(kw)
        await asyncio.sleep(5)
        return _FakeResponse()


def test_timeout_controlled_single_attempt(monkeypatch):
    models = _SlowModels()
    monkeypatch.setattr(gp, "_get_client", lambda api_key: _FakeClient(models))
    monkeypatch.setenv("AI_TIMEOUT_S", "0.05")
    with pytest.raises(HTTPException) as e:
        _run(GeminiProvider("k", "m").generate("S", MSGS))
    assert e.value.status_code == 504
    assert len(models.calls) == 1  # expired request is cancelled, never repeated


# =============== 5. Usage metadata absent ===============
class TestUsageMetadata:
    def test_missing_attribute_is_fine(self, fake):
        out = _run(GeminiProvider("k", "m").generate("S", MSGS))
        assert isinstance(out, str)

    def test_none_metadata_is_fine(self, fake):
        fake.queue.append(_FakeResponse(text="{}", usage=None))
        out = _run(GeminiProvider("k", "m").generate("S", MSGS))
        assert out == "{}"

    def test_present_metadata_logged(self, fake, caplog):
        fake.queue.append(_FakeResponse(text="{}", usage=_FakeUsage(100, 20)))
        with caplog.at_level(logging.INFO, logger="services.ai.gemini_provider"):
            _run(GeminiProvider("k", "m").generate("S", MSGS))
        assert any("tokens_in=100" in r.getMessage() and "tokens_out=20" in r.getMessage() for r in caplog.records)


# =============== 6. Client lifecycle ===============
class TestClientLifecycle:
    def test_same_loop_reuses_client(self):
        gp._clients.clear()

        async def scenario():
            a = gp._get_client("dummy-key-not-real")
            b = gp._get_client("dummy-key-not-real")
            assert a is b
        _run(scenario())

    def test_new_loop_gets_new_client(self):
        gp._clients.clear()
        first = _run(_id_client("dummy-key-not-real"))
        second = _run(_id_client("dummy-key-not-real"))
        assert first != second  # no cross-event-loop reuse

    def test_different_key_different_client(self):
        gp._clients.clear()

        async def scenario():
            a = gp._get_client("key-A")
            b = gp._get_client("key-B")
            assert a is not b
        _run(scenario())

    def test_client_cache_bounded(self):
        gp._clients.clear()
        for i in range(gp._MAX_CLIENTS + 2):
            asyncio.run(_id_client(f"key-{i}"))
        assert len(gp._clients) <= gp._MAX_CLIENTS


async def _id_client(key):
    return id(gp._get_client(key))


# =============== 7. No automatic retry ===============
class TestNoRetry:
    def test_error_is_single_attempt(self, fake):
        fake.queue.append(genai_errors.ServerError(503, {"error": {"message": "down"}}))
        with pytest.raises(HTTPException):
            _run(GeminiProvider("k", "m").generate("S", MSGS))
        assert len(fake.calls) == 1

    def test_success_is_single_attempt(self, fake):
        _run(GeminiProvider("k", "m").generate("S", MSGS))
        assert len(fake.calls) == 1

    def test_sdk_retry_disabled_by_default(self, monkeypatch):
        monkeypatch.setattr(gp, "_clients", {})
        disabled = _run(_check_retry_off())
        assert disabled is True


async def _check_retry_off():
    client = gp._get_client("dummy-key-not-real")
    return client._api_client._http_options.retry_options is None


# =============== 8. Log hygiene ===============
class TestLogHygiene:
    def test_success_logs_contain_no_prompt_nor_pii_nor_key(self, fake, caplog):
        with caplog.at_level(logging.DEBUG, logger="services.ai.gemini_provider"):
            _run(GeminiProvider("SECRET-API-KEY-XYZ", "m").generate(PROMPT, MSGS))
        blob = " | ".join(r.getMessage() for r in caplog.records)
        for forbidden in ("SECRET-PROMPT-SYSTEM", "0707070707", "client@exemple.ci",
                          "PII-USER", "Jean Kouassi", "SECRET-API-KEY-XYZ"):
            assert forbidden not in blob
        assert any("gemini_call" in r.getMessage() for r in caplog.records)

    def test_error_logs_contain_no_prompt_nor_pii_nor_key(self, fake, caplog):
        fake.queue.append(genai_errors.ClientError(429, {"error": {"message": "quota hit"}}))
        with caplog.at_level(logging.DEBUG, logger="services.ai.gemini_provider"):
            with pytest.raises(HTTPException):
                _run(GeminiProvider("SECRET-API-KEY-XYZ", "m").generate(PROMPT, MSGS))
        blob = " | ".join(r.getMessage() for r in caplog.records)
        for forbidden in ("SECRET-PROMPT-SYSTEM", "0707070707", "client@exemple.ci",
                          "PII-USER", "Jean Kouassi", "SECRET-API-KEY-XYZ", "quota hit"):
            assert forbidden not in blob
        assert any("category=api" in r.getMessage() and "429" in r.getMessage() for r in caplog.records)


# =============== Factory ===============
class TestFactory:
    def test_gemini_selected(self, monkeypatch):
        monkeypatch.setenv("AI_GATEWAY", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
        p = get_configured_provider()
        assert isinstance(p, GeminiProvider)
        assert p.model == "gemini-2.5-flash"

    def test_no_fallback_bytez(self, monkeypatch):
        monkeypatch.setenv("AI_GATEWAY", "bytez")
        monkeypatch.setenv("AI_MODEL", "google/gemini-2.5-flash")
        monkeypatch.setenv("BYTEZ_API_KEY", "k")
        monkeypatch.setenv("BYTEZ_PROVIDER_KEY", "p")
        from services.ai.bytez_provider import BytezProvider
        assert isinstance(get_configured_provider(), BytezProvider)

    def test_missing_key_503(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(HTTPException) as e:
            get_default_provider()
        assert e.value.status_code == 503
