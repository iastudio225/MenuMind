from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId

# ---- Roles ----
SUPER_ADMIN = "SUPER_ADMIN"
RESTAURANT_OWNER = "RESTAURANT_OWNER"
RESTAURANT_MANAGER = "RESTAURANT_MANAGER"
RESTAURANT_STAFF = "RESTAURANT_STAFF"

RESTAURANT_ROLES = [RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF]
ALL_ROLES = [SUPER_ADMIN] + RESTAURANT_ROLES


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def oid(value: str) -> ObjectId:
    return ObjectId(value)


def serialize(doc: Optional[dict], drop: Optional[List[str]] = None) -> Optional[dict]:
    """Convert a Mongo document to a JSON-safe dict: _id -> id (str), strip sensitive fields."""
    if doc is None:
        return None
    out = dict(doc)
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    for field in (drop or []):
        out.pop(field, None)
    return out


# ---- Request / Response models ----
class RegisterBody(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=6)
    restaurant_name: str = Field(min_length=1)
    phone: Optional[str] = ""


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str
    password: str = Field(min_length=6)


class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    opening_hours: Optional[Dict[str, Any]] = None
    widget: Optional[Dict[str, Any]] = None
    onboarding_completed: Optional[bool] = None


class UserCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=6)
    role: str


class UserUpdate(BaseModel):
    role: Optional[str] = None
    active: Optional[bool] = None
    name: Optional[str] = None


class AdminRestaurantCreate(BaseModel):
    name: str
    owner_name: str
    owner_email: EmailStr
    owner_password: str = Field(min_length=6)
    plan: Optional[str] = "STARTER"


class RestaurantStatusUpdate(BaseModel):
    status: str  # active | suspended


class AdminRestaurantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    plan: Optional[str] = None
    plan_expires_at: Optional[str] = None  # ISO date, null = sans expiration


class PlanCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(min_length=1)
    price: int = Field(ge=0)
    currency: str = "FCFA"
    limits: Dict[str, Any] = {}


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = Field(default=None, ge=0)
    currency: Optional[str] = None
    limits: Optional[Dict[str, Any]] = None
