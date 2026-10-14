from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db
from auth import require_roles, get_current_user, tenant_id_of
from models import serialize, now_iso, RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF

router = APIRouter(prefix="/delivery", tags=["delivery"])
MANAGE = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER)
VIEW = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF)


class ZoneCreate(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = ""
    fee: int = Field(ge=0)
    active: Optional[bool] = True


class ZoneUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    fee: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None


def _oid(v):
    try:
        return ObjectId(v)
    except Exception:
        raise HTTPException(status_code=400, detail="Identifiant invalide")


@router.get("/zones")
async def list_zones(user: dict = Depends(VIEW)):
    rid = tenant_id_of(user)
    docs = await db.delivery_zones.find({"restaurant_id": rid}).sort("fee", 1).to_list(500)
    return [serialize(d) for d in docs]


@router.post("/zones")
async def create_zone(body: ZoneCreate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    ts = now_iso()
    doc = {"restaurant_id": rid, "name": body.name.strip(), "description": body.description or "",
           "fee": int(body.fee), "active": body.active if body.active is not None else True,
           "created_at": ts, "updated_at": ts}
    res = await db.delivery_zones.insert_one(doc)
    doc["_id"] = res.inserted_id
    await db.audit_logs.insert_one({"restaurant_id": rid, "user_id": user["_id"],
                                    "action": "ZONE_CREATE", "detail": body.name, "created_at": ts})
    return serialize(doc)


@router.patch("/zones/{zone_id}")
async def update_zone(zone_id: str, body: ZoneUpdate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    zone = await db.delivery_zones.find_one({"_id": _oid(zone_id), "restaurant_id": rid})
    if not zone:
        raise HTTPException(status_code=404, detail="Zone introuvable")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    if "fee" in updates:
        updates["fee"] = int(updates["fee"])
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    updates["updated_at"] = now_iso()
    await db.delivery_zones.update_one({"_id": _oid(zone_id)}, {"$set": updates})
    doc = await db.delivery_zones.find_one({"_id": _oid(zone_id)})
    return serialize(doc)


@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: str, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    zone = await db.delivery_zones.find_one({"_id": _oid(zone_id), "restaurant_id": rid})
    if not zone:
        raise HTTPException(status_code=404, detail="Zone introuvable")
    await db.delivery_zones.delete_one({"_id": _oid(zone_id)})
    await db.audit_logs.insert_one({"restaurant_id": rid, "user_id": user["_id"],
                                    "action": "ZONE_DELETE", "detail": zone_id, "created_at": now_iso()})
    return {"message": "Zone supprimée"}
