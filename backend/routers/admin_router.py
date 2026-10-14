import secrets
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from database import db
from models import (AdminRestaurantCreate, RestaurantStatusUpdate, serialize, now_iso,
                    SUPER_ADMIN, RESTAURANT_OWNER)
from auth import require_roles, hash_password
from routers.auth_router import default_opening_hours

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics")
async def metrics(user: dict = Depends(require_roles(SUPER_ADMIN))):
    total = await db.restaurants.count_documents({})
    active = await db.restaurants.count_documents({"status": "active"})
    suspended = await db.restaurants.count_documents({"status": "suspended"})
    total_orders = await db.orders.count_documents({})

    plan_prices = {"STARTER": 15000, "BUSINESS": 30000, "PRO": 50000}
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
    docs = await db.restaurants.find({}).sort("created_at", -1).to_list(1000)
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
    return [serialize(d) for d in docs]
