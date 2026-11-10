"""Offline tests for seed startup policy and credentialed CORS configuration."""
from starlette.middleware.cors import CORSMiddleware

from config import LOCAL_FRONTEND_ORIGINS, cors_origins, maybe_run_startup_seed, seed_on_startup


def _run_immediate(coro):
    try:
        coro.send(None)
    except StopIteration as done:
        return done.value
    raise RuntimeError("Coroutine unexpectedly yielded external I/O")


def test_development_defaults_to_no_startup_seed():
    calls = []

    async def seed():
        calls.append("seed")

    assert not seed_on_startup({"MENUMIND_ENV": "development"})
    assert _run_immediate(maybe_run_startup_seed({"MENUMIND_ENV": "development"}, seed)) is False
    assert calls == []


def test_explicit_seed_and_production_default_preserve_seed_behavior():
    assert seed_on_startup({"MENUMIND_ENV": "development", "MENUMIND_SEED_ON_STARTUP": "true"})
    assert seed_on_startup({"MENUMIND_ENV": "production"})
    assert not seed_on_startup({"MENUMIND_ENV": "production", "MENUMIND_SEED_ON_STARTUP": "false"})
    calls = []

    async def seed():
        calls.append("seed")

    assert _run_immediate(maybe_run_startup_seed(
        {"MENUMIND_ENV": "development", "MENUMIND_SEED_ON_STARTUP": "true"}, seed)) is True
    assert calls == ["seed"]


def _cors_preflight(origin, allowed_origins):
    sent = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = CORSMiddleware(
        app,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "OPTIONS",
        "path": "/api/auth/login",
        "raw_path": b"/api/auth/login",
        "query_string": b"",
        "headers": [
            (b"origin", origin.encode("ascii")),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"content-type"),
        ],
        "server": ("127.0.0.1", 8001),
        "client": ("127.0.0.1", 40000),
        "scheme": "http",
    }
    _run_immediate(middleware(scope, receive, send))
    start = next(message for message in sent if message["type"] == "http.response.start")
    return start["status"], dict(start.get("headers", []))


def test_local_origins_are_credential_safe_and_nonlocal_origin_is_denied():
    origins = cors_origins({"MENUMIND_ENV": "development", "CORS_ORIGINS": "*"})
    assert all(origin in origins for origin in LOCAL_FRONTEND_ORIGINS)
    assert "*" not in origins

    for origin in LOCAL_FRONTEND_ORIGINS:
        status, headers = _cors_preflight(origin, origins)
        assert status == 200
        assert headers[b"access-control-allow-origin"].decode() == origin
        assert headers[b"access-control-allow-credentials"] == b"true"

    status, headers = _cors_preflight("http://evil.example", origins)
    assert status == 400
    assert b"access-control-allow-origin" not in headers


def test_local_origins_are_not_added_to_production_allowlist():
    origins = cors_origins({"MENUMIND_ENV": "production", "FRONTEND_URL": "https://app.example"})
    assert origins == ["https://app.example"]
    for origin in LOCAL_FRONTEND_ORIGINS:
        status, _ = _cors_preflight(origin, origins)
        assert status == 400
