"""Tenant webhook configuration test endpoint (n8n orchestration)."""
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from database import db
from auth import require_roles, tenant_id_of
from models import RESTAURANT_OWNER, RESTAURANT_MANAGER
from services import notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])
MANAGE = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER)


@router.post("/test")
async def send_test_event(user: dict = Depends(MANAGE)):
    """Send a sample event to the tenant's configured n8n webhook."""
    rid = tenant_id_of(user)
    restaurant = await db.restaurants.find_one({"_id": ObjectId(rid)})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    if not notifications.webhook_url_for(restaurant):
        raise HTTPException(status_code=400, detail="Aucun webhook configuré pour cet établissement")
    return await notifications.dispatch(db, restaurant, "test", {
        "message": "Événement de test MenuMind",
        "restaurant_name": restaurant.get("name", ""),
    })
