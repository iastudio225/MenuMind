import secrets
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from database import db
from models import (AdminRestaurantCreate, AdminRestaurantUpdate, RestaurantStatusUpdate,
                    PlanCreate, PlanUpdate, UserPasswordUpdate, serialize, now_iso,
                    SUPER_ADMIN, RESTAURANT_OWNER)
from auth import require_roles, hash_password
from routers.auth_router import default_opening_hours

router = APIRouter(prefix="/admin", tags=["admin"])

EDITABLE_RESTAURANT_FIELDS = ("name", "description", "phone", "whatsapp", "email",
                              "address", "city")


async def plan_assignments_count(code: str) -> int:
    return await db.restaurants.count_documents({"plan": code, "status": {"$ne": "deleted"}})


@router.get("/metrics")
async def metrics(user: dict = Depends(require_roles(SUPER_ADMIN))):
    not_deleted = {"status": {"$ne": "deleted"}}
    total = await db.restaurants.count_documents(not_deleted)
    active = await db.restaurants.count_documents({"status": "active"})
    suspended = await db.restaurants.count_documents({"status": "suspended"})
    total_orders = await db.orders.count_documents({})

    plan_prices = {"STARTER": 15000, "BUSINESS": 30000, "PRO": 50000}
    for p in await db.plans.find({}).to_list(100):
        plan_prices[p["code"]] = p.get("price", 0)
    active_docs = await db.restaurants.find({"status": "active"}).to_list(10000)
    mrr = sum(plan_prices.get(r.get("plan", "STARTER"), 0) for r in active_docs)

    ai_convos = await db.ai_conversations.count_documents({})
    return {
        "total_restaurants": total,
        "active_restaurants": active,
        "suspended_restaurants": suspended,
        "total_orders": total_orders,
        "estimated_mrr": mrr,
        "ai_conversations": ai_convos,
    }


@router.get("/restaurants")
async def list_restaurants(user: dict = Depends(require_roles(SUPER_ADMIN))):
    docs = await db.restaurants.find({"status": {"$ne": "deleted"}}).sort("created_at", -1).to_list(1000)
    result = []
    for d in docs:
        rid = str(d["_id"])
        owner = await db.users.find_one({"restaurant_id": rid, "role": RESTAURANT_OWNER})
        orders = await db.orders.count_documents({"restaurant_id": rid})
        s = serialize(d)
        s["owner_email"] = owner["email"] if owner else None
        s["orders_count"] = orders
        result.append(s)
    return result


@router.get("/restaurants/{restaurant_id}")
async def restaurant_detail(restaurant_id: str, user: dict = Depends(require_roles(SUPER_ADMIN))):
    doc = await db.restaurants.find_one({"_id": ObjectId(restaurant_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    users = await db.users.find({"restaurant_id": restaurant_id}).to_list(500)
    s = serialize(doc)
    s["users"] = [serialize(u, drop=["password_hash"]) for u in users]
    s["orders_count"] = await db.orders.count_documents({"restaurant_id": restaurant_id})
    return s


@router.patch("/restaurants/{restaurant_id}/status")
async def set_status(restaurant_id: str, body: RestaurantStatusUpdate,
                     user: dict = Depends(require_roles(SUPER_ADMIN))):
    if body.status not in ("active", "suspended"):
        raise HTTPException(status_code=400, detail="Statut invalide")
    res = await db.restaurants.update_one({"_id": ObjectId(restaurant_id)},
                                          {"$set": {"status": body.status, "updated_at": now_iso()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    await db.audit_logs.insert_one({"restaurant_id": restaurant_id, "user_id": user["_id"],
                                    "action": "RESTAURANT_STATUS", "detail": body.status, "created_at": now_iso()})
    return {"message": f"Restaurant {body.status}"}


@router.patch("/restaurants/{restaurant_id}")
async def update_restaurant(restaurant_id: str, body: AdminRestaurantUpdate,
                            user: dict = Depends(require_roles(SUPER_ADMIN))):
    doc = await db.restaurants.find_one({"_id": ObjectId(restaurant_id),
                                         "status": {"$ne": "deleted"}})
    if not doc:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    updates = body.model_dump(exclude_unset=True)
    if "plan" in updates and updates["plan"]:
        if not await db.plans.find_one({"code": updates["plan"]}):
            raise HTTPException(status_code=400, detail="Plan inexistant")
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    updates["updated_at"] = now_iso()
    await db.restaurants.update_one({"_id": ObjectId(restaurant_id)}, {"$set": updates})
    await db.audit_logs.insert_one({"restaurant_id": restaurant_id, "user_id": user["_id"],
                                    "action": "RESTAURANT_UPDATE",
                                     "detail": {k: updates.get(k) for k in
                                                ("plan", "plan_activated_at", "plan_expires_at", "name", "city")},
                                    "created_at": now_iso()})
    return {"message": "Restaurant mis à jour"}


@router.delete("/restaurants/{restaurant_id}")
async def delete_restaurant(restaurant_id: str,
                            user: dict = Depends(require_roles(SUPER_ADMIN))):
    doc = await db.restaurants.find_one({"_id": ObjectId(restaurant_id)})
    if not doc or doc.get("status") == "deleted":
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    await db.restaurants.update_one(
        {"_id": ObjectId(restaurant_id)},
        {"$set": {"status": "deleted", "deleted_at": now_iso(), "updated_at": now_iso()}})
    await db.audit_logs.insert_one({"restaurant_id": restaurant_id, "user_id": user["_id"],
                                    "action": "RESTAURANT_DELETE", "detail": "soft-delete",
                                    "created_at": now_iso()})
    return {"message": "Restaurant supprimé"}


@router.patch("/users/{user_id}/password")
async def reset_user_password(user_id: str, body: UserPasswordUpdate,
                              user: dict = Depends(require_roles(SUPER_ADMIN))):
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password_hash": hash_password(body.password)}, "$inc": {"token_version": 1}})
    await db.audit_logs.insert_one({"user_id": user["_id"],
                                    "action": "USER_PASSWORD_RESET",
                                    "detail": {"target_user_id": user_id, "target_email": doc["email"]},
                                    "created_at": now_iso()})
    return {"message": "Mot de passe réinitialisé"}


@router.post("/restaurants")
async def create_restaurant(body: AdminRestaurantCreate, user: dict = Depends(require_roles(SUPER_ADMIN))):
    email = body.owner_email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    ts = now_iso()
    public_id = "rest_" + secrets.token_hex(6)
    rdoc = {
        "public_id": public_id, "name": body.name, "description": "", "logo": "", "phone": "",
        "whatsapp": "", "email": email, "address": "", "city": "", "country": "Côte d'Ivoire",
        "currency": "FCFA", "timezone": "Africa/Abidjan", "opening_hours": default_opening_hours(),
        "status": "active", "plan": body.plan or "STARTER", "onboarding_completed": False,
        "widget": {"primary_color": "#E05638", "secondary_color": "#0F172A",
                   "welcome_message": f"Bonjour 👋 Bienvenue chez {body.name} !", "logo": ""},
        "created_at": ts, "updated_at": ts,
    }
    res = await db.restaurants.insert_one(rdoc)
    rid = str(res.inserted_id)
    udoc = {"email": email, "password_hash": hash_password(body.owner_password), "name": body.owner_name,
            "role": RESTAURANT_OWNER, "restaurant_id": rid, "token_version": 0, "active": True, "created_at": ts}
    ures = await db.users.insert_one(udoc)
    await db.restaurants.update_one({"_id": res.inserted_id}, {"$set": {"owner_id": str(ures.inserted_id)}})
    return serialize({**rdoc, "_id": res.inserted_id})


@router.get("/plans")
async def list_plans(user: dict = Depends(require_roles(SUPER_ADMIN))):
    docs = await db.plans.find({}).to_list(100)
    out = []
    for d in docs:
        s = serialize(d)
        s["restaurants_count"] = await plan_assignments_count(d["code"])
        out.append(s)
    return out


@router.post("/plans")
async def create_plan(body: PlanCreate, user: dict = Depends(require_roles(SUPER_ADMIN))):
    if await db.plans.find_one({"code": body.code}):
        raise HTTPException(status_code=400, detail="Ce code de plan existe déjà")
    ts = now_iso()
    doc = {"code": body.code, "name": body.name, "price": body.price,
           "currency": body.currency, "limits": body.limits, "created_at": ts, "updated_at": ts}
    res = await db.plans.insert_one(doc)
    await db.audit_logs.insert_one({"user_id": user["_id"], "action": "PLAN_CREATE",
                                    "detail": body.code, "created_at": ts})
    return serialize({**doc, "_id": res.inserted_id})


@router.patch("/plans/{code}")
async def update_plan(code: str, body: PlanUpdate,
                      user: dict = Depends(require_roles(SUPER_ADMIN))):
    doc = await db.plans.find_one({"code": code})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan introuvable")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    updates["updated_at"] = now_iso()
    await db.plans.update_one({"code": code}, {"$set": updates})
    await db.audit_logs.insert_one({"user_id": user["_id"], "action": "PLAN_UPDATE",
                                    "detail": {code: list(updates.keys())}, "created_at": now_iso()})
    return {"message": "Plan mis à jour"}


@router.delete("/plans/{code}")
async def delete_plan(code: str, user: dict = Depends(require_roles(SUPER_ADMIN))):
    doc = await db.plans.find_one({"code": code})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan introuvable")
    if await plan_assignments_count(code) > 0:
        raise HTTPException(status_code=409,
                            detail="Plan assigné à un ou plusieurs restaurants — "
                                   "réassignez-les avant de le supprimer")
    await db.plans.delete_one({"code": code})
    await db.audit_logs.insert_one({"user_id": user["_id"], "action": "PLAN_DELETE",
                                    "detail": code, "created_at": now_iso()})
    return {"message": "Plan supprimé"}
