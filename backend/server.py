from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from database import db, get_client
from seed import run_seed
from routers import (auth_router, restaurant_router, user_router, dashboard_router,
                     admin_router, menu_router, cart_router, order_router,
                     customer_router, delivery_router, ai_router, embed_router,
                     weekly_menu_router)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="MenuMind API")

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

_frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
_origins = [_frontend_url]
if os.environ.get("CORS_ORIGINS") and os.environ.get("CORS_ORIGINS") != "*":
    _origins += os.environ["CORS_ORIGINS"].split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    try:
        await run_seed()
    except Exception as e:
        logger.error("Erreur lors du seed: %s", e)


@app.on_event("shutdown")
async def shutdown_db_client():
    get_client().close()
