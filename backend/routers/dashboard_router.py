from fastapi import APIRouter, Depends
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from database import db
from auth import get_current_user, tenant_id_of

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    rid = tenant_id_of(user)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=7)).isoformat()

    return await db.dashboard_overview(rid, today, week_start)
