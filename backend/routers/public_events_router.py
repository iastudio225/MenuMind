"""Public, unauthenticated visit events used for link attribution.

Only a minimal payload is stored (restaurant, kind, source, session id). No IP
address, no user agent, no customer data — see the 90-day retention note in the
plan. Visits are deduplicated per (restaurant, session) so reloads and the React
StrictMode double-mount cannot inflate the counts.
"""
import time
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import db
from models import now_iso
from services.attribution import normalize_source

router = APIRouter(prefix="/public", tags=["public-events"])

# Best-effort, in-process abuse guard (same spirit as services/ai/quota.py).
MAX_EVENTS_PER_MINUTE = 5
_WINDOW_SECONDS = 60
_recent: dict[str, list[float]] = {}


class PublicEventBody(BaseModel):
    public_id: str = Field(min_length=1, max_length=128)
    kind: Literal["visit"]
    source: Optional[str] = ""
    session_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


def reset_rate_limits() -> None:
    """Test helper — clears the in-process event window."""
    _recent.clear()


def _allow(session_id: str) -> bool:
    now = time.monotonic()
    cutoff = now - _WINDOW_SECONDS
    hits = [stamp for stamp in _recent.get(session_id, []) if stamp > cutoff]
    if len(hits) >= MAX_EVENTS_PER_MINUTE:
        _recent[session_id] = hits
        return False
    hits.append(now)
    _recent[session_id] = hits
    if len(_recent) > 5000:  # global purge, bounded memory
        for key in [k for k, v in _recent.items() if not v or v[-1] <= cutoff]:
            _recent.pop(key, None)
    return True


@router.post("/events", status_code=202)
async def record_event(body: PublicEventBody):
    restaurant = await db.restaurants.find_one(
        {"public_id": body.public_id, "status": "active"})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")

    restaurant_id = str(restaurant["_id"])
    query = {"restaurant_id": restaurant_id, "kind": body.kind, "session_id": body.session_id}
    if await db.public_events.find_one(query):
        return {"recorded": False}
    if not _allow(body.session_id):
        raise HTTPException(status_code=429, detail="Trop d'évènements")

    try:
        await db.public_events.insert_one({
            **query,
            "source": normalize_source(body.source),
            "created_at": now_iso(),
        })
    except Exception as exc:  # unique index race — the event is already counted
        if "duplicate key" in str(exc).lower():
            return {"recorded": False}
        raise
    return {"recorded": True}
