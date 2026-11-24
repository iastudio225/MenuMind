import secrets
import asyncio
import os
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from database import db
from models import (AdminRestaurantCreate, AdminRestaurantUpdate, RestaurantStatusUpdate,
                    PlanCreate, PlanUpdate, UserPasswordUpdate, AISettingsUpdate,
                    serialize, now_iso, SUPER_ADMIN, RESTAURANT_OWNER,
                    normalize_secteur, validate_ai_settings, AI_PROVIDERS)
from auth import require_roles, hash_password
from routers.auth_router import default_opening_hours, default_widget_message
from services.ai.provider import effective_ai_settings, get_provider_for_restaurant

router = APIRouter(prefix="/admin", tags=["admin"])

EDITABLE_RESTAURANT_FIELDS = ("name", "description", "phone", "whatsapp", "email",
                              "address", "city")


async def plan_assignments_count(code: str) -> int:
    return await db.restaurants.count_documents({"plan": code, "status": {"$ne": "deleted"}})


@router.get("/ai-settings")
async def get_ai_settings(user: dict = Depends(require_roles(SUPER_ADMIN))):
    doc = await db.platform_settings.find_one({"_id": "ai"})
    settings = None
    if doc and doc.get("provider") and doc.get("model"):
        settings = {"provider": doc.get("provider"), "model": doc.get("model")}
    return {
        "settings": settings,
        "env": {
            "gateway": os.environ.get("AI_GATEWAY") or os.environ.get("AI_PROVIDER") or "gemini",
            "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            "bytez_model": os.environ.get("AI_MODEL", ""),
        },
        "keys": {
            "gemini": bool(os.environ.get("GEMINI_API_KEY")),
            "bytez": bool(os.environ.get("BYTEZ_API_KEY")),
            "bytez_provider": bool(os.environ.get("BYTEZ_PROVIDER_KEY")),
        },
        "providers": list(AI_PROVIDERS),
    }


@router.patch("/ai-settings")
async def update_ai_settings(body: AISettingsUpdate, user: dict = Depends(require_roles(SUPER_ADMIN))):
    try:
        ai = validate_ai_settings(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not ai:
        raise HTTPException(status_code=400, detail="Configuration IA invalide")
    ts = now_iso()
    await db.platform_settings.update_one(
        {"_id": "ai"},
        {"$set": {**ai, "updated_at": ts, "updated_by": user["_id"]}},
        upsert=True,
    )
    await db.audit_logs.insert_one({"user_id": user["_id"], "action": "AI_SETTINGS_UPDATE",
                                    "detail": ai, "created_at": ts})
    return {"settings": ai}


@router.post("/ai-settings/test")
async def test_ai_settings(user: dict = Depends(require_roles(SUPER_ADMIN))):
    platform = await db.platform_settings.find_one({"_id": "ai"})
    try:
        provider = get_provider_for_restaurant({}, None, platform)
        sample = await provider.generate(
            "Tu es un test de configuration. Réponds uniquement par OK.",
            [{"role": "user", "content": "OK"}],
        )
        return {"ok": True, "sample": str(sample)[:200]}
    except HTTPException as exc:
        return {"ok": False, "detail": exc.detail}
    except Exception:
        return {"ok": False, "detail": "Échec du test du modèle"}


@router.get("/metrics")
async def metrics(user: dict = Depends(require_roles(SUPER_ADMIN))):
    not_deleted = {"status": {"$ne": "deleted"}}
    total, active, suspended, total_orders, plans, active_docs, ai_convos = await asyncio.gather(
        db.restaurants.count_documents(not_deleted),
        db.restaurants.count_documents({"status": "active"}),
        db.restaurants.count_documents({"status": "suspended"}),
        db.orders.count_documents({}),
        db.plans.find({}).to_list(100),
        db.restaurants.find({"status": "active"}).to_list(10000),
        db.ai_conversations.count_documents({}),
    )
    plan_prices = {"STARTER": 15000, "BUSINESS": 30000, "PRO": 50000}
    for p in plans:
        plan_prices[p["code"]] = p.get("price", 0)
    mrr = sum(plan_prices.get(r.get("plan", "STARTER"), 0) for r in active_docs)
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
    return [serialize(doc) for doc in await db.admin_restaurants_with_stats()]


@router.get("/restaurants/{restaurant_id}")
async def restaurant_detail(restaurant_id: str, user: dict = Depends(require_roles(SUPER_ADMIN))):
    doc = await db.restaurants.find_one({"_id": ObjectId(restaurant_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    users = await db.users.find({"restaurant_id": restaurant_id}).to_list(500)
    s = serialize(doc)
    s["users"] = [serialize(u, drop=["password_hash"]) for u in users]
    s["orders_count"] = await db.orders.count_documents({"restaurant_id": restaurant_id})
    plan = await db.plans.find_one({"code": s.get("plan")}) if s.get("plan") else None
    platform = await db.platform_settings.find_one({"_id": "ai"})
    s["effective_ai"] = effective_ai_settings(s, plan, platform)
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
    secteur = normalize_secteur(body.secteur)
    rdoc = {
        "public_id": public_id, "name": body.name, "description": "", "logo": "", "phone": "",
        "whatsapp": "", "email": email, "address": "", "city": "", "country": "Côte d'Ivoire",
        "currency": "FCFA", "timezone": "Africa/Abidjan", "opening_hours": default_opening_hours(),
        "status": "active", "plan": body.plan or "STARTER", "onboarding_completed": False,
        "secteur": secteur,
        "widget": {"primary_color": "#E05638", "secondary_color": "#0F172A",
                   "welcome_message": default_widget_message(body.name, secteur), "logo": ""},
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
