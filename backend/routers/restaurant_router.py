from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from database import db
from models import (RestaurantUpdate, serialize, now_iso,
                    RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF)
from auth import get_current_user, tenant_id_of, require_roles

router = APIRouter(prefix="/restaurants", tags=["restaurants"])
MANAGE = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER)


@router.get("/me")
async def get_my_restaurant(user: dict = Depends(get_current_user)):
    rid = tenant_id_of(user)
    doc = await db.restaurants.find_one({"_id": ObjectId(rid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    doc = serialize(doc)
    # Le secret de signature du webhook ne doit pas être lisible par un STAFF.
    if user.get("role") == RESTAURANT_STAFF and isinstance(doc.get("notifications"), dict):
        doc["notifications"] = {k: v for k, v in doc["notifications"].items() if k != "webhook_secret"}
    return doc


@router.patch("/me")
async def update_my_restaurant(body: RestaurantUpdate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    updates["updated_at"] = now_iso()
    await db.restaurants.update_one({"_id": ObjectId(rid)}, {"$set": updates})
    await db.audit_logs.insert_one({"restaurant_id": rid, "user_id": user["_id"],
                                    "action": "RESTAURANT_UPDATE", "detail": ",".join(updates.keys()),
                                    "created_at": now_iso()})
    doc = await db.restaurants.find_one({"_id": ObjectId(rid)})
    return serialize(doc)


@router.get("/public/{public_id}")
async def get_public_restaurant(public_id: str):
    """Non-sensitive data only — used later by the embeddable widget."""
    doc = await db.restaurants.find_one({"public_id": public_id, "status": "active"})
    if not doc:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    return {
        "public_id": doc["public_id"],
        "name": doc.get("name"),
        "secteur": doc.get("secteur", "restaurant"),
        "logo": doc.get("logo"),
        "currency": doc.get("currency"),
        "widget": doc.get("widget", {}),
    }
