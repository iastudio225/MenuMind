import os
import logging
from pathlib import Path
from datetime import datetime, timezone

from database import db
from auth import hash_password, verify_password
from models import SUPER_ADMIN, RESTAURANT_OWNER, now_iso
from routers.auth_router import default_opening_hours

logger = logging.getLogger(__name__)

DEMO_OWNER_EMAIL = "awa@chezawa.ci"
DEMO_OWNER_PASSWORD = "Demo1234!"


async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("restaurant_id")
    await db.restaurants.create_index("public_id", unique=True)
    await db.restaurants.create_index("status")
    await db.menu_items.create_index("restaurant_id")
    await db.menu_items.create_index([("restaurant_id", 1), ("category_id", 1)])
    await db.menu_items.create_index([("restaurant_id", 1), ("display_order", 1)])
    await db.menu_categories.create_index("restaurant_id")
    await db.menu_categories.create_index([("restaurant_id", 1), ("display_order", 1)])
    await db.menu_option_groups.create_index("restaurant_id")
    await db.menu_options.create_index("restaurant_id")
    await db.menu_options.create_index([("restaurant_id", 1), ("group_id", 1)])
    await db.orders.create_index("restaurant_id")
    await db.orders.create_index([("restaurant_id", 1), ("status", 1)])
    await db.orders.create_index([("restaurant_id", 1), ("created_at", -1)])
    await db.orders.create_index([("restaurant_id", 1), ("customer_id", 1)])
    await db.orders.create_index("tracking_token")
    await db.orders.create_index([("restaurant_id", 1), ("idempotency_key", 1)], sparse=True)
    await db.carts.create_index("cart_id", unique=True)
    await db.carts.create_index("restaurant_id")
    await db.customers.create_index("restaurant_id")
    await db.customers.create_index([("restaurant_id", 1), ("phone", 1)])
    await db.order_status_history.create_index([("restaurant_id", 1), ("order_id", 1)])
    await db.ai_conversations.create_index("conversation_id", unique=True)
    await db.ai_conversations.create_index("restaurant_id")
    await db.ai_conversations.create_index("updated_at")
    await db.delivery_zones.create_index("restaurant_id")
    await db.audit_logs.create_index("restaurant_id")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("token_hash", unique=True)
    await db.login_attempts.create_index("email")
    await db.login_attempts.create_index("identifier")
    await db.password_reset_requests.create_index("email")
    await db.password_reset_requests.create_index("created_at", expireAfterSeconds=900)


async def seed_super_admin():
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({
            "email": email, "password_hash": hash_password(password), "name": "Super Admin",
            "role": SUPER_ADMIN, "restaurant_id": None, "token_version": 0,
            "active": True, "created_at": now_iso(),
        })
        logger.info("Super admin seedé: %s", email)
    elif not verify_password(password, existing.get("password_hash", "")):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})


async def seed_plans():
    plans = [
        {"code": "STARTER", "name": "Starter", "price": 15000, "currency": "FCFA",
         "limits": {"max_orders_per_month": 300, "max_ai_conversations": 500, "max_users": 2,
                    "whatsapp_enabled": False, "analytics_enabled": False, "custom_branding": False}},
        {"code": "BUSINESS", "name": "Business", "price": 30000, "currency": "FCFA",
         "limits": {"max_orders_per_month": -1, "max_ai_conversations": 5000, "max_users": 10,
                    "whatsapp_enabled": True, "analytics_enabled": True, "custom_branding": True}},
        {"code": "PRO", "name": "Pro", "price": 50000, "currency": "FCFA",
         "limits": {"max_orders_per_month": -1, "max_ai_conversations": -1, "max_users": -1,
                    "whatsapp_enabled": True, "analytics_enabled": True, "custom_branding": True}},
    ]
    for p in plans:
        await db.plans.update_one({"code": p["code"]}, {"$set": p}, upsert=True)


async def seed_demo_restaurant():
    existing = await db.restaurants.find_one({"name": "Chez Awa"})
    if existing:
        return
    ts = now_iso()
    rdoc = {
        "public_id": "rest_demo_chezawa", "name": "Chez Awa",
        "description": "Maquis ivoirien — grillades, poissons et plats traditionnels.",
        "logo": "", "phone": "+2250700000000", "whatsapp": "+2250700000000", "email": DEMO_OWNER_EMAIL,
        "address": "Rue des Jardins, Cocody", "city": "Abidjan", "country": "Côte d'Ivoire",
        "currency": "FCFA", "timezone": "Africa/Abidjan", "opening_hours": default_opening_hours(),
        "status": "active", "plan": "BUSINESS", "onboarding_completed": True,
        "widget": {"primary_color": "#E05638", "secondary_color": "#0F172A",
                   "welcome_message": "Bonjour 👋 Bienvenue chez Awa ! Que souhaitez-vous commander ?", "logo": ""},
        "created_at": ts, "updated_at": ts,
    }
    res = await db.restaurants.insert_one(rdoc)
    rid = str(res.inserted_id)

    owner = await db.users.find_one({"email": DEMO_OWNER_EMAIL})
    if not owner:
        ures = await db.users.insert_one({
            "email": DEMO_OWNER_EMAIL, "password_hash": hash_password(DEMO_OWNER_PASSWORD), "name": "Awa Koné",
            "role": RESTAURANT_OWNER, "restaurant_id": rid, "token_version": 0, "active": True, "created_at": ts,
        })
        await db.restaurants.update_one({"_id": res.inserted_id}, {"$set": {"owner_id": str(ures.inserted_id)}})

    cat_plats = await db.menu_categories.insert_one(
        {"restaurant_id": rid, "name": "Plats", "description": "Nos plats principaux",
         "display_order": 1, "active": True, "created_at": ts, "updated_at": ts})
    cat_boissons = await db.menu_categories.insert_one(
        {"restaurant_id": rid, "name": "Boissons", "description": "Rafraîchissements",
         "display_order": 2, "active": True, "created_at": ts, "updated_at": ts})

    plats = [
        {"name": "Poulet braisé", "price": 5000, "description": "Poulet braisé à la braise"},
        {"name": "Poulet braisé + alloco", "price": 5500, "description": "Avec bananes plantain frites"},
        {"name": "Poulet braisé + attiéké", "price": 5500, "description": "Avec attiéké"},
        {"name": "Poisson braisé", "price": 6000, "description": "Poisson frais braisé"},
    ]
    boissons = [
        {"name": "Coca-Cola", "price": 1000, "description": "33cl"},
        {"name": "Fanta", "price": 1000, "description": "33cl"},
        {"name": "Eau", "price": 500, "description": "50cl"},
    ]
    order = 1
    for it in plats:
        await db.menu_items.insert_one({"restaurant_id": rid, "category_id": str(cat_plats.inserted_id),
                                        "name": it["name"], "description": it["description"], "image": "",
                                        "price": it["price"], "active": True, "available": True,
                                        "display_order": order, "created_at": ts, "updated_at": ts})
        order += 1
    order = 1
    for it in boissons:
        await db.menu_items.insert_one({"restaurant_id": rid, "category_id": str(cat_boissons.inserted_id),
                                        "name": it["name"], "description": it["description"], "image": "",
                                        "price": it["price"], "active": True, "available": True,
                                        "display_order": order, "created_at": ts, "updated_at": ts})
        order += 1

    zones = [("Cocody", 1000), ("Marcory", 1500), ("Yopougon", 2000)]
    for name, fee in zones:
        await db.delivery_zones.insert_one({"restaurant_id": rid, "name": name, "description": "",
                                            "fee": fee, "active": True, "created_at": ts, "updated_at": ts})
    logger.info("Restaurant de démonstration 'Chez Awa' seedé")


async def seed_demo_menu_extras():
    """Idempotent: backfill image_url/option_group_ids and add demo option groups to Chez Awa."""
    restaurant = await db.restaurants.find_one({"name": "Chez Awa"})
    if not restaurant:
        return
    rid = str(restaurant["_id"])
    ts = now_iso()

    # Backfill fields on legacy items (Phase A used "image" and had no option_group_ids)
    await db.menu_items.update_many(
        {"restaurant_id": rid, "image_url": {"$exists": False}},
        [{"$set": {"image_url": {"$ifNull": ["$image", ""]}}}])
    await db.menu_items.update_many(
        {"restaurant_id": rid, "option_group_ids": {"$exists": False}},
        {"$set": {"option_group_ids": []}})

    # Seed option groups only once
    if await db.menu_option_groups.find_one({"restaurant_id": rid, "name": "Accompagnement"}):
        return

    g_acc = await db.menu_option_groups.insert_one({
        "restaurant_id": rid, "name": "Accompagnement", "description": "Choisissez votre accompagnement",
        "required": True, "min_selections": 1, "max_selections": 1, "display_order": 1,
        "active": True, "created_at": ts, "updated_at": ts})
    gid_acc = str(g_acc.inserted_id)
    for i, name in enumerate(["Alloco", "Attiéké", "Frites"], start=1):
        await db.menu_options.insert_one({
            "restaurant_id": rid, "group_id": gid_acc, "name": name, "description": "", "price_delta": 0,
            "active": True, "available": True, "display_order": i, "created_at": ts, "updated_at": ts})

    g_sup = await db.menu_option_groups.insert_one({
        "restaurant_id": rid, "name": "Suppléments", "description": "Ajoutez des suppléments",
        "required": False, "min_selections": 0, "max_selections": 5, "display_order": 2,
        "active": True, "created_at": ts, "updated_at": ts})
    gid_sup = str(g_sup.inserted_id)
    for i, (name, delta) in enumerate([("Fromage", 500), ("Œuf", 500), ("Viande", 1000)], start=1):
        await db.menu_options.insert_one({
            "restaurant_id": rid, "group_id": gid_sup, "name": name, "description": "", "price_delta": delta,
            "active": True, "available": True, "display_order": i, "created_at": ts, "updated_at": ts})

    # Attach groups to "Poulet braisé" (base) and "Poisson braisé"
    await db.menu_items.update_one(
        {"restaurant_id": rid, "name": "Poulet braisé"},
        {"$set": {"option_group_ids": [gid_acc, gid_sup], "updated_at": ts}})
    await db.menu_items.update_one(
        {"restaurant_id": rid, "name": "Poisson braisé"},
        {"$set": {"option_group_ids": [gid_acc], "updated_at": ts}})
    logger.info("Options de démonstration 'Chez Awa' seedées")


async def write_test_credentials():
    content = f"""# Test Credentials

## Super Admin (plateforme SaaS)
- Email: {os.environ.get('ADMIN_EMAIL')}
- Password: {os.environ.get('ADMIN_PASSWORD')}
- Role: SUPER_ADMIN

## Restaurant de démonstration "Chez Awa" (propriétaire)
- Email: {DEMO_OWNER_EMAIL}
- Password: {DEMO_OWNER_PASSWORD}
- Role: RESTAURANT_OWNER

## Auth endpoints
- POST /api/auth/register  (name, email, password, restaurant_name, phone)
- POST /api/auth/login     (email, password)
- POST /api/auth/logout
- GET  /api/auth/me
- POST /api/auth/refresh
- POST /api/auth/forgot-password  (email)
- POST /api/auth/reset-password   (token, password)

## Notes
- Roles: SUPER_ADMIN, RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF
- Multi-tenant: chaque donnée liée à restaurant_id, isolée via le token JWT (httpOnly cookie).
"""
    Path("/app/memory").mkdir(parents=True, exist_ok=True)
    Path("/app/memory/test_credentials.md").write_text(content)


async def run_seed():
    await ensure_indexes()
    await seed_super_admin()
    await seed_plans()
    await seed_demo_restaurant()
    await seed_demo_menu_extras()
    await write_test_credentials()
