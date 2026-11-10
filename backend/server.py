import os
from pathlib import Path
from dotenv import dotenv_values, load_dotenv

ROOT_DIR = Path(__file__).parent
MENUMIND_ENV = (
    os.environ.get("MENUMIND_ENV")
    or dotenv_values(ROOT_DIR / ".env").get("MENUMIND_ENV")
    or "development"
).strip().lower()
os.environ.setdefault("MENUMIND_ENV", MENUMIND_ENV)

is_development = MENUMIND_ENV in {"development", "dev", "local", "test"}
env_file = ".env.development.local" if is_development else ".env"
load_dotenv(ROOT_DIR / env_file, override=False)

import logging
import time
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from config import cors_origins, maybe_run_startup_seed
from database import db, get_client
from seed import run_seed
from routers import (auth_router, restaurant_router, user_router, dashboard_router,
                     admin_router, menu_router, cart_router, order_router,
                     customer_router, delivery_router, ai_router, embed_router,
                     weekly_menu_router)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="MenuMind API")


@app.middleware("http")
async def log_slow_api_requests(request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    path = request.url.path
    if path.startswith("/api/") and elapsed_ms >= 250:
        logger.warning("Slow API request method=%s path=%s status=%s duration_ms=%.1f",
                       request.method, path, response.status_code, elapsed_ms)
    return response

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "MenuMind API", "status": "ok"}


@api_router.get("/plans")
async def public_plans():
    docs = await db.plans.find({}).sort("price", 1).to_list(100)
    out = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


app.include_router(api_router)
app.include_router(auth_router.router, prefix="/api")
app.include_router(restaurant_router.router, prefix="/api")
app.include_router(user_router.router, prefix="/api")
app.include_router(dashboard_router.router, prefix="/api")
app.include_router(admin_router.router, prefix="/api")
app.include_router(menu_router.router, prefix="/api")
app.include_router(weekly_menu_router.router, prefix="/api")
app.include_router(cart_router.router, prefix="/api")
app.include_router(order_router.router, prefix="/api")
app.include_router(order_router.public_router, prefix="/api")
app.include_router(customer_router.router, prefix="/api")
app.include_router(delivery_router.router, prefix="/api")
app.include_router(ai_router.router, prefix="/api")
app.include_router(ai_router.console_router, prefix="/api")
app.include_router(embed_router.router)

_origins = cors_origins(os.environ)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await db.connect()
    try:
        did_seed = await maybe_run_startup_seed(os.environ, run_seed)
        if not did_seed:
            logger.info("Seed de démarrage ignoré (MENUMIND_ENV=%s)",
                        os.environ.get("MENUMIND_ENV", "development"))
    except Exception:
        logger.exception("Erreur lors du seed")


@app.on_event("shutdown")
async def shutdown_db_client():
    await get_client().close()
