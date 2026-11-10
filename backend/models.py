from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Literal
import re
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
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
    plan_activated_at: Optional[str] = None  # ISO date, null = non définie
    plan_expires_at: Optional[str] = None  # ISO date, null = sans expiration


class UserPasswordUpdate(BaseModel):
    password: str = Field(min_length=6)


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


# License history contracts are separate from the legacy restaurant date
# strings. No persistence or conversion is performed by these models.
LicenseAction = Literal["CREATE", "RENEW", "CHANGE_PLAN", "ADMIN_CORRECTION"]
LicenseStatus = Literal["UNASSIGNED", "DATA_INCOMPLETE", "NOT_STARTED", "ACTIVE", "EXPIRED"]
LicenseType = Literal["TRIAL", "PAID"]
LicenseOperationState = Literal["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED_RETRYABLE", "FAILED_FINAL"]
PendingRegistrationOrigin = Literal["PUBLIC", "ADMIN"]
PendingRegistrationState = Literal["PENDING_VERIFICATION", "VERIFIED", "FINALIZING", "FINALIZED", "FAILED_RETRYABLE", "EXPIRED"]
ACTIVE_PENDING_REGISTRATION_STATES = (
    "PENDING_VERIFICATION", "VERIFIED", "FINALIZING", "FAILED_RETRYABLE",
)
VerificationTokenState = Literal["ACTIVE", "USED", "INVALIDATED", "EXPIRED"]
ConversionRequestState = Literal["PENDING", "APPROVED", "REJECTED"]


def normalize_email(email: str) -> str:
    """Normalize outer/inter-token whitespace and case, preserving . and +."""
    return " ".join(email.split()).lower()


def _require_aware_datetime(value):
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Un fuseau horaire est obligatoire")
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Un fuseau horaire est obligatoire")
    else:
        raise ValueError("Un datetime avec fuseau horaire est obligatoire")
    return value


def _normalized_email_must_be_valid(value: str) -> str:
    if not isinstance(value, str) or value != normalize_email(value):
        raise ValueError("L'adresse doit être préalablement normalisée")
    if (not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}", value)
            or value.split("@", 1)[0].startswith(".")
            or value.split("@", 1)[0].endswith(".")
            or ".." in value.split("@", 1)[0]):
        raise ValueError("Adresse e-mail invalide")
    return value


class VerificationRateLimits(BaseModel):
    link_validity_hours: int = Field(default=24, gt=0)
    resend_cooldown_seconds: int = Field(default=60, ge=0)
    email_requests_per_hour: int = Field(default=5, gt=0)
    ip_requests_per_hour: int = Field(default=20, gt=0)


class LicensePeriod(BaseModel):
    plan_code: str = Field(min_length=2, max_length=20)
    license_type: LicenseType
    start_at: datetime
    end_at: datetime
    price_snapshot: int = Field(ge=0)
    currency: str = Field(min_length=1)

    @field_validator("start_at", "end_at", mode="before")
    @classmethod
    def require_aware_datetime(cls, value):
        return _require_aware_datetime(value)

    @model_validator(mode="after")
    def validate_period_order(self):
        if self.end_at.astimezone(timezone.utc) <= self.start_at.astimezone(timezone.utc):
            raise ValueError("end_at doit être strictement postérieur à start_at")
        return self


class LicenseHistoryEntry(LicensePeriod):
    restaurant_id: str = Field(min_length=1)
    action: LicenseAction
    previous_plan_code: Optional[str] = None
    created_by: str = Field(min_length=1)
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def require_aware_created_at(cls, value):
        return _require_aware_datetime(value)


class LicenseOperation(BaseModel):
    operation_id: str = Field(min_length=1)
    operation_type: str = Field(min_length=1)
    state: LicenseOperationState = "PENDING"
    restaurant_id: Optional[str] = None
    history_entry_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_error_code: Optional[str] = None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def require_aware_timestamps(cls, value):
        return _require_aware_datetime(value)

    @model_validator(mode="after")
    def validate_timestamps(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at doit être supérieur ou égal à created_at")
        return self


class PendingRegistration(BaseModel):
    origin: PendingRegistrationOrigin
    email_normalized: str = Field(min_length=3)
    created_by_admin_id: Optional[str] = None
    state: PendingRegistrationState = "PENDING_VERIFICATION"
    created_at: datetime
    expires_at: datetime
    cleanup_at: Optional[datetime] = None
    verification_generation: int = Field(default=1, ge=1)
    operation_id: Optional[str] = None
    user_id: Optional[str] = None
    restaurant_id: Optional[str] = None
    email_verified_at: Optional[datetime] = None

    @field_validator("email_normalized")
    @classmethod
    def require_normalized_email(cls, value):
        return _normalized_email_must_be_valid(value)

    @field_validator("created_at", "expires_at", "cleanup_at", "email_verified_at", mode="before")
    @classmethod
    def require_aware_timestamps(cls, value):
        return None if value is None else _require_aware_datetime(value)

    @model_validator(mode="after")
    def validate_origin_fields(self):
        if self.origin == "ADMIN" and not self.created_by_admin_id:
            raise ValueError("created_by_admin_id est requis pour origin=ADMIN")
        if self.origin == "PUBLIC" and self.created_by_admin_id is not None:
            raise ValueError("created_by_admin_id doit être absent pour origin=PUBLIC")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at doit être postérieur à created_at")
        if self.cleanup_at is not None and self.cleanup_at < self.expires_at:
            raise ValueError("cleanup_at ne peut précéder expires_at")
        if self.state in {"VERIFIED", "FINALIZING", "FINALIZED"} and self.email_verified_at is None:
            raise ValueError("Un état vérifié exige email_verified_at")
        if self.state == "PENDING_VERIFICATION" and self.email_verified_at is not None:
            raise ValueError("Une inscription en attente ne peut pas être vérifiée")
        if self.state == "FINALIZED" and (not self.user_id or not self.restaurant_id):
            raise ValueError("Une inscription finalisée exige user_id et restaurant_id")
        if self.state == "FINALIZED" and self.cleanup_at is not None:
            raise ValueError("Une inscription finalisée ne doit pas avoir cleanup_at")
        if self.state in {"PENDING_VERIFICATION", "VERIFIED", "EXPIRED"} and (
            self.user_id is not None or self.restaurant_id is not None
        ):
            raise ValueError("Une inscription non finalisée ne peut référencer un compte ou restaurant")
        if self.state == "FINALIZING" and ((self.user_id is None) != (self.restaurant_id is None)):
            raise ValueError("Une finalisation partielle doit conserver les deux références ensemble")
        if self.state in {"PENDING_VERIFICATION", "EXPIRED"} and self.cleanup_at is None:
            raise ValueError("Une inscription temporaire doit avoir cleanup_at")
        if self.state in {"VERIFIED", "FINALIZING", "FAILED_RETRYABLE"} and self.cleanup_at is not None:
            raise ValueError("Une inscription vérifiée ou récupérable ne doit pas être nettoyée par TTL")
        return self


class EmailVerificationToken(BaseModel):
    token_hash: str = Field(min_length=1)
    pending_registration_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    state: VerificationTokenState = "ACTIVE"
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime] = None

    @field_validator("created_at", "expires_at", "used_at", mode="before")
    @classmethod
    def require_aware_timestamps(cls, value):
        return None if value is None else _require_aware_datetime(value)

    @model_validator(mode="after")
    def validate_state_timestamps(self):
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at doit être postérieur à created_at")
        if self.state == "USED":
            if self.used_at is None or not self.created_at <= self.used_at < self.expires_at:
                raise ValueError("Un jeton USED exige used_at dans sa période de validité")
        elif self.used_at is not None:
            raise ValueError("used_at est autorisé uniquement pour un jeton USED")
        return self


class VerificationRateLimitCounter(BaseModel):
    key_hash: str = Field(min_length=1)
    scope: Literal["EMAIL", "IP"]
    window_started_at: datetime
    request_timestamps: List[datetime] = Field(default_factory=list)
    updated_at: datetime

    @field_validator("window_started_at", "request_timestamps", "updated_at", mode="before")
    @classmethod
    def require_aware_timestamps(cls, value):
        if isinstance(value, list):
            return [_require_aware_datetime(item) for item in value]
        return _require_aware_datetime(value)

    @model_validator(mode="after")
    def validate_window(self):
        if self.updated_at < self.window_started_at:
            raise ValueError("updated_at précède window_started_at")
        if any(item < self.window_started_at or item > self.updated_at for item in self.request_timestamps):
            raise ValueError("request_timestamps hors de la fenêtre du compteur")
        return self


class TrialEligibility(BaseModel):
    email_normalized: str = Field(min_length=3)
    state: Literal["RESERVED", "CONSUMED"]
    operation_id: str = Field(min_length=1)
    restaurant_id: Optional[str] = None
    history_entry_id: Optional[str] = None
    reserved_at: datetime
    consumed_at: Optional[datetime] = None

    @field_validator("email_normalized")
    @classmethod
    def require_normalized_email(cls, value):
        return _normalized_email_must_be_valid(value)

    @field_validator("reserved_at", "consumed_at", mode="before")
    @classmethod
    def require_aware_timestamps(cls, value):
        return None if value is None else _require_aware_datetime(value)

    @model_validator(mode="after")
    def validate_consumption(self):
        if self.state == "CONSUMED":
            if not self.consumed_at or not self.restaurant_id or not self.history_entry_id:
                raise ValueError("Un trial consommé exige consumed_at, restaurant_id et history_entry_id")
            if self.consumed_at < self.reserved_at:
                raise ValueError("consumed_at ne peut précéder reserved_at")
        elif self.consumed_at is not None or self.restaurant_id is not None or self.history_entry_id is not None:
            raise ValueError("Un trial réservé ne peut avoir de date de consommation ni de références")
        return self


class LicenseConversionRequest(BaseModel):
    request_id: str = Field(min_length=1)
    restaurant_id: str = Field(min_length=1)
    requested_plan_code: str = Field(min_length=2, max_length=20)
    state: ConversionRequestState = "PENDING"
    requested_by: str = Field(min_length=1)
    requested_at: datetime
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    operation_id: Optional[str] = None

    @field_validator("requested_at", "decided_at", mode="before")
    @classmethod
    def require_aware_timestamps(cls, value):
        return None if value is None else _require_aware_datetime(value)

    @model_validator(mode="after")
    def validate_decision(self):
        has_decision = self.decided_by is not None or self.decided_at is not None
        if self.state == "PENDING":
            if has_decision:
                raise ValueError("Une demande PENDING ne peut porter de décision")
        elif not self.decided_by or self.decided_at is None:
            raise ValueError("Une demande décidée exige decided_by et decided_at")
        if self.decided_at is not None and self.decided_at < self.requested_at:
            raise ValueError("decided_at ne peut précéder requested_at")
        return self
