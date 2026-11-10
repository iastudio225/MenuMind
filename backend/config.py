"""Pure environment-derived application settings.

Keep this module free of database imports so startup policy and CORS can be
tested without opening a Mongo client or running application startup hooks.
"""


PRODUCTION_ENVIRONMENTS = {"production", "prod"}
DEVELOPMENT_ENVIRONMENTS = {"development", "dev", "local", "test"}
LOCAL_FRONTEND_ORIGINS = (
    "http://localhost:3001",
    "http://localhost:3000",
    "http://localhost:3003",
    "http://127.0.0.1:3001",
)


def seed_on_startup(environ):
    """Default to no seed locally; retain it in production unless overridden."""
    mode = (environ.get("MENUMIND_ENV") or "development").strip().lower()
    default = mode in PRODUCTION_ENVIRONMENTS
    raw = environ.get("MENUMIND_SEED_ON_STARTUP")
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError("MENUMIND_SEED_ON_STARTUP must be a boolean value")


async def maybe_run_startup_seed(environ, seed_runner):
    """Run the supplied seed only when the environment policy enables it."""
    if not seed_on_startup(environ):
        return False
    await seed_runner()
    return True


def cors_origins(environ):
    """Build credential-safe CORS origins; local origins apply only in dev."""
    mode = (environ.get("MENUMIND_ENV") or "development").strip().lower()
    origins = []
    frontend = (environ.get("FRONTEND_URL") or "http://localhost:3000").strip().rstrip("/")
    if frontend and frontend != "*":
        origins.append(frontend)

    extras = environ.get("CORS_ORIGINS", "")
    origins.extend(origin.strip().rstrip("/") for origin in extras.split(",")
                   if origin.strip() and origin.strip() != "*")

    if mode in DEVELOPMENT_ENVIRONMENTS:
        origins.extend(LOCAL_FRONTEND_ORIGINS)

    # Stable order and exact-string de-duplication.
    return list(dict.fromkeys(origin for origin in origins if origin))
