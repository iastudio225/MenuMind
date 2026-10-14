import os
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Response, Request, HTTPException, BackgroundTasks, Depends

from database import db
from models import (RegisterBody, LoginBody, ForgotPasswordBody, ResetPasswordBody,
                    RESTAURANT_OWNER, serialize, now_iso)
from auth import (hash_password, verify_password, set_auth_cookies, clear_auth_cookies,
                  get_current_user, create_access_token, send_password_reset_email,
                  sha256_hex, get_jwt_secret)
import jwt as pyjwt

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_ATTEMPTS = 5
LOCK_MINUTES = 15
RESET_MAX = 5
RESET_WINDOW_MIN = 15
RESET_APP_MAX = 10  # app-wide window matches shared sender quota


def default_opening_hours():
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return {d: {"open": "11:00", "close": "22:00", "closed": False} for d in days}


def _user_public(user_doc: dict) -> dict:
    return serialize(user_doc, drop=["password_hash"])


@router.post("/register")
async def register(body: RegisterBody, response: Response):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    ts = now_iso()
    public_id = "rest_" + secrets.token_hex(6)
    restaurant_doc = {
        "public_id": public_id, "name": body.restaurant_name, "description": "", "logo": "",
        "phone": body.phone or "", "whatsapp": "", "email": email,
        "address": "", "city": "", "country": "Côte d'Ivoire", "currency": "FCFA",
        "timezone": "Africa/Abidjan", "opening_hours": default_opening_hours(),
        "status": "active", "plan": "STARTER", "onboarding_completed": False,
        "widget": {"primary_color": "#E05638", "secondary_color": "#0F172A",
                   "welcome_message": f"Bonjour 👋 Bienvenue chez {body.restaurant_name} !", "logo": ""},
        "created_at": ts, "updated_at": ts,
    }
    res = await db.restaurants.insert_one(restaurant_doc)
    rid = str(res.inserted_id)
    user_doc = {
        "email": email, "password_hash": hash_password(body.password), "name": body.name,
        "role": RESTAURANT_OWNER, "restaurant_id": rid, "token_version": 0,
        "active": True, "created_at": ts,
    }
    ures = await db.users.insert_one(user_doc)
    uid = str(ures.inserted_id)
    await db.restaurants.update_one({"_id": res.inserted_id}, {"$set": {"owner_id": uid}})
    await db.audit_logs.insert_one({"restaurant_id": rid, "user_id": uid, "action": "USER_REGISTER",
                                    "detail": email, "created_at": ts})
    user_doc["_id"] = ures.inserted_id
    set_auth_cookies(response, uid, email, 0)
    return _user_public(user_doc)


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response):
    email = body.email.lower().strip()
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    identifier = f"{ip}:{email}"
    now = datetime.now(timezone.utc)

    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= MAX_ATTEMPTS:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > now:
            raise HTTPException(status_code=429, detail="Trop de tentatives. Réessayez dans quelques minutes.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        locked_until = (now + timedelta(minutes=LOCK_MINUTES)).isoformat()
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"email": email, "locked_until": locked_until, "updated_at": now.isoformat()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Compte désactivé")

    await db.login_attempts.delete_many({"identifier": identifier})
    await db.audit_logs.insert_one({"restaurant_id": user.get("restaurant_id"), "user_id": str(user["_id"]),
                                    "action": "USER_LOGIN", "detail": email, "created_at": now_iso()})
    set_auth_cookies(response, str(user["_id"]), email, user.get("token_version", 0))
    return _user_public(user)


@router.post("/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    clear_auth_cookies(response)
    return {"message": "Déconnecté"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Pas de token de rafraîchissement")
    try:
        payload = pyjwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Type de token invalide")
        from bson import ObjectId
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user or payload.get("ver", 0) != user.get("token_version", 0):
            raise HTTPException(status_code=401, detail="Session expirée")
        access = create_access_token(str(user["_id"]), user["email"], user.get("token_version", 0))
        response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=900, path="/")
        return {"message": "ok"}
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")


GENERIC_RESET = {"message": "Si cet email est enregistré, un lien de réinitialisation a été envoyé."}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordBody, background_tasks: BackgroundTasks):
    email = body.email.lower().strip()
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(minutes=RESET_WINDOW_MIN)).isoformat()
    await db.password_reset_requests.insert_one({"email": email, "created_at": now.isoformat()})

    email_count = await db.password_reset_requests.count_documents({"email": email, "created_at": {"$gte": window_start}})
    app_count = await db.password_reset_requests.count_documents({"created_at": {"$gte": window_start}})
    if email_count > RESET_MAX or app_count > RESET_APP_MAX:
        return GENERIC_RESET

    user = await db.users.find_one({"email": email})
    if not user:
        return GENERIC_RESET

    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token_hash": sha256_hex(token), "user_id": str(user["_id"]), "email": email,
        "expires_at": (now + timedelta(hours=1)).isoformat(), "used": False, "created_at": now.isoformat(),
    })
    background_tasks.add_task(send_password_reset_email, user["email"], token)
    return GENERIC_RESET


@router.post("/reset-password")
async def reset_password(body: ResetPasswordBody):
    now = datetime.now(timezone.utc)
    h = sha256_hex(body.token)
    doc = await db.password_reset_tokens.find_one_and_update(
        {"token_hash": h, "used": False, "expires_at": {"$gt": now.isoformat()}},
        {"$set": {"used": True}},
    )
    if not doc:
        raise HTTPException(status_code=400, detail="Lien invalide ou expiré")
    from bson import ObjectId
    uid = doc["user_id"]
    await db.users.update_one(
        {"_id": ObjectId(uid)},
        {"$set": {"password_hash": hash_password(body.password)}, "$inc": {"token_version": 1}},
    )
    await db.password_reset_tokens.delete_many({"user_id": uid, "used": False})
    await db.login_attempts.delete_many({"email": doc["email"]})
    return {"message": "Mot de passe réinitialisé. Vous pouvez vous connecter."}
