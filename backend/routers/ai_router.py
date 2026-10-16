import time
import logging
from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db
from auth import get_current_user, tenant_id_of
from services.ai import agent_service
from services.ai.provider import get_configured_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public/ai", tags=["ai"])

# Simple in-process rate limiter: max N requests / window per IP
_WINDOW = 60
_MAX = 20
_MAX_IP_KEYS = 5000  # memory bound: purge dead IP keys beyond this
_hits = defaultdict(list)


def _purge_dead_ips(now: float):
    """Remove IP keys whose entries are all expired (bounded memory)."""
    dead = [ip for ip, hits in _hits.items() if not hits or now - max(hits) >= _WINDOW]
    for ip in dead:
        del _hits[ip]


def _rate_limit(ip: str):
    now = time.time()
    hits = [t for t in _hits[ip] if now - t < _WINDOW]
    if len(hits) >= _MAX:
        raise HTTPException(status_code=429, detail="Trop de requêtes. Patientez un instant.")
    hits.append(now)
    _hits[ip] = hits
    if len(_hits) >= _MAX_IP_KEYS:
        _purge_dead_ips(now)


class ChatBody(BaseModel):
    restaurant_public_id: str
    conversation_id: Optional[str] = None
    # D1.50: panier partagé — le menu visuel crée le panier et passe son
    # cart_id ; le backend valide existence/restaurant/statut avant liaison.
    cart_id: Optional[str] = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=1000)


@router.post("/chat")
async def chat(body: ChatBody, request: Request):
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
    _rate_limit(ip)
    provider = get_configured_provider()
    return await agent_service.process_message(
        db, body.restaurant_public_id, body.conversation_id, body.message, provider,
        cart_id=body.cart_id)


# ---- Console de test dashboard (authenticated, tenant derive de la session) ----
console_router = APIRouter(prefix="/ai", tags=["ai-console"])


class TestChatBody(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=1000)


@console_router.post("/test/chat")
async def test_chat(body: TestChatBody, user: dict = Depends(get_current_user)):
    # Le restaurant n'est JAMAIS lu depuis le body: il est derive de la session
    # authentifiee. Un conversation_id d'un autre tenant est ignore par
    # agent_service._get_or_create_conversation (nouvelle conversation locale).
    rid = tenant_id_of(user)
    restaurant = await db.restaurants.find_one({"_id": ObjectId(rid)})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    provider = get_configured_provider()
    return await agent_service.process_message(
        db, restaurant["public_id"], body.conversation_id, body.message, provider)
