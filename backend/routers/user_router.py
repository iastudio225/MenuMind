from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from database import db
from models import (UserCreate, UserUpdate, serialize, now_iso,
                    RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF, RESTAURANT_ROLES)
from auth import get_current_user, tenant_id_of, hash_password

router = APIRouter(prefix="/users", tags=["users"])

MANAGE_ROLES = [RESTAURANT_OWNER, RESTAURANT_MANAGER]


@router.get("")
async def list_users(user: dict = Depends(get_current_user)):
    rid = tenant_id_of(user)
    docs = await db.users.find({"restaurant_id": rid}).to_list(500)
    return [serialize(d, drop=["password_hash"]) for d in docs]


@router.post("")
async def create_user(body: UserCreate, user: dict = Depends(get_current_user)):
    if user["role"] != RESTAURANT_OWNER:
        raise HTTPException(status_code=403, detail="Seul le propriétaire peut créer des utilisateurs")
    rid = tenant_id_of(user)
    if body.role not in RESTAURANT_ROLES:
        raise HTTPException(status_code=400, detail="Rôle invalide")
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    ts = now_iso()
    doc = {"email": email, "password_hash": hash_password(body.password), "name": body.name,
           "role": body.role, "restaurant_id": rid, "token_version": 0, "active": True, "created_at": ts}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    await db.audit_logs.insert_one({"restaurant_id": rid, "user_id": user["_id"],
                                    "action": "USER_CREATE", "detail": f"{email}:{body.role}", "created_at": ts})
    return serialize(doc, drop=["password_hash"])


@router.patch("/{user_id}")
async def update_user(user_id: str, body: UserUpdate, user: dict = Depends(get_current_user)):
    if user["role"] != RESTAURANT_OWNER:
        raise HTTPException(status_code=403, detail="Seul le propriétaire peut modifier les utilisateurs")
    rid = tenant_id_of(user)
    target = await db.users.find_one({"_id": ObjectId(user_id), "restaurant_id": rid})
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if target["_id"] == ObjectId(user["_id"]) and body.active is False:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous désactiver vous-même")
    updates = {}
    if body.role is not None:
        if body.role not in RESTAURANT_ROLES:
            raise HTTPException(status_code=400, detail="Rôle invalide")
        updates["role"] = body.role
    if body.active is not None:
        updates["active"] = body.active
    if body.name is not None:
        updates["name"] = body.name
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    await db.audit_logs.insert_one({"restaurant_id": rid, "user_id": user["_id"],
                                    "action": "USER_UPDATE", "detail": f"{user_id}:{updates}", "created_at": now_iso()})
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    return serialize(doc, drop=["password_hash"])


@router.delete("/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != RESTAURANT_OWNER:
        raise HTTPException(status_code=403, detail="Seul le propriétaire peut supprimer des utilisateurs")
    rid = tenant_id_of(user)
    if user_id == user["_id"]:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous supprimer")
    target = await db.users.find_one({"_id": ObjectId(user_id), "restaurant_id": rid})
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if target.get("role") == RESTAURANT_OWNER:
        raise HTTPException(status_code=400, detail="Impossible de supprimer le propriétaire")
    await db.users.delete_one({"_id": ObjectId(user_id)})
    await db.audit_logs.insert_one({"restaurant_id": rid, "user_id": user["_id"],
                                    "action": "USER_DELETE", "detail": user_id, "created_at": now_iso()})
    return {"message": "Utilisateur supprimé"}
