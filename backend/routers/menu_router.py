from typing import Optional, List, Dict, Any
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db
from models import (serialize, now_iso, RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF)
from auth import get_current_user, require_roles, tenant_id_of
from services.order_service import item_in_stock

router = APIRouter(prefix="/menu", tags=["menu"])

# Roles that can change menu structure (categories, items, options)
MANAGE = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER)
# Roles that can at least view / toggle availability
VIEW = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER, RESTAURANT_STAFF)


# ---------- Request models ----------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = ""
    display_order: Optional[int] = None
    active: Optional[bool] = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    display_order: Optional[int] = None
    active: Optional[bool] = None


class ItemCreate(BaseModel):
    category_id: str
    name: str = Field(min_length=1)
    description: Optional[str] = ""
    image_url: Optional[str] = ""
    price: int = Field(ge=0)
    active: Optional[bool] = True
    available: Optional[bool] = True
    display_order: Optional[int] = None
    option_group_ids: Optional[List[str]] = None
    pricing_rules: Optional[Dict[str, Any]] = None
    stock: Optional[int] = Field(default=None, ge=0)
    sku: Optional[str] = ""


class ItemUpdate(BaseModel):
    category_id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None
    available: Optional[bool] = None
    display_order: Optional[int] = None
    option_group_ids: Optional[List[str]] = None
    pricing_rules: Optional[Dict[str, Any]] = None
    stock: Optional[int] = Field(default=None, ge=0)
    sku: Optional[str] = None


class AvailabilityUpdate(BaseModel):
    available: bool


class ReorderBody(BaseModel):
    ids: List[str]
    category_id: Optional[str] = None


class OptionGroupCreate(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = ""
    required: Optional[bool] = False
    min_selections: int = Field(default=0, ge=0)
    max_selections: int = Field(default=1, ge=0)
    display_order: Optional[int] = None
    active: Optional[bool] = True


class OptionGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    required: Optional[bool] = None
    min_selections: Optional[int] = Field(default=None, ge=0)
    max_selections: Optional[int] = Field(default=None, ge=0)
    display_order: Optional[int] = None
    active: Optional[bool] = None


class OptionCreate(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = ""
    price_delta: int = Field(default=0, ge=0)
    active: Optional[bool] = True
    available: Optional[bool] = True
    display_order: Optional[int] = None
    stock: Optional[int] = Field(default=None, ge=0)


class OptionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    price_delta: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None
    available: Optional[bool] = None
    display_order: Optional[int] = None
    stock: Optional[int] = Field(default=None, ge=0)


class VariantCreate(BaseModel):
    option_ids: List[str] = Field(min_length=1)
    sku: Optional[str] = ""
    price_delta: int = Field(default=0, ge=0)
    stock: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = True


class VariantUpdate(BaseModel):
    option_ids: Optional[List[str]] = None
    sku: Optional[str] = None
    price_delta: Optional[int] = Field(default=None, ge=0)
    stock: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None


# ---------- Helpers ----------
def _oid(value: str, label: str = "identifiant") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{label} invalide")


async def _own_category(rid: str, category_id: str) -> dict:
    cat = await db.menu_categories.find_one({"_id": _oid(category_id, "catégorie"), "restaurant_id": rid})
    if not cat:
        raise HTTPException(status_code=400, detail="Catégorie introuvable pour ce restaurant")
    return cat


async def _validate_option_groups(rid: str, ids: List[str]):
    for gid in ids:
        g = await db.menu_option_groups.find_one({"_id": _oid(gid, "groupe d'options"), "restaurant_id": rid})
        if not g:
            raise HTTPException(status_code=400, detail="Groupe d'options introuvable pour ce restaurant")


async def _next_order(collection, rid: str, extra: Optional[dict] = None) -> int:
    q = {"restaurant_id": rid}
    if extra:
        q.update(extra)
    last = await collection.find(q).sort("display_order", -1).limit(1).to_list(1)
    return (last[0].get("display_order", 0) + 1) if last else 1


def _log(rid, uid, action, detail):
    return db.audit_logs.insert_one({"restaurant_id": rid, "user_id": uid, "action": action,
                                     "detail": str(detail), "created_at": now_iso()})


# ================= CATEGORIES =================
@router.get("/categories")
async def list_categories(user: dict = Depends(VIEW)):
    rid = tenant_id_of(user)
    docs = await db.menu_categories.find({"restaurant_id": rid}).sort("display_order", 1).to_list(500)
    return [serialize(d) for d in docs]


@router.post("/categories")
async def create_category(body: CategoryCreate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    ts = now_iso()
    order = body.display_order if body.display_order is not None else await _next_order(db.menu_categories, rid)
    doc = {"restaurant_id": rid, "name": body.name.strip(), "description": body.description or "",
           "display_order": order, "active": body.active if body.active is not None else True,
           "created_at": ts, "updated_at": ts}
    res = await db.menu_categories.insert_one(doc)
    doc["_id"] = res.inserted_id
    await _log(rid, user["_id"], "MENU_CATEGORY_CREATE", body.name)
    return serialize(doc)


@router.patch("/categories/{category_id}")
async def update_category(category_id: str, body: CategoryUpdate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    await _own_category(rid, category_id)
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    updates["updated_at"] = now_iso()
    await db.menu_categories.update_one({"_id": _oid(category_id)}, {"$set": updates})
    await _log(rid, user["_id"], "MENU_CATEGORY_UPDATE", f"{category_id}:{list(updates.keys())}")
    doc = await db.menu_categories.find_one({"_id": _oid(category_id)})
    return serialize(doc)


@router.delete("/categories/{category_id}")
async def delete_category(category_id: str, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    await _own_category(rid, category_id)
    count = await db.menu_items.count_documents({"restaurant_id": rid, "category_id": category_id})
    if count > 0:
        raise HTTPException(status_code=400,
                            detail=f"Cette catégorie contient {count} article(s). Déplacez ou supprimez-les d'abord, ou désactivez la catégorie.")
    await db.menu_categories.delete_one({"_id": _oid(category_id)})
    await _log(rid, user["_id"], "MENU_CATEGORY_DELETE", category_id)
    return {"message": "Catégorie supprimée"}


@router.post("/categories/reorder")
async def reorder_categories(body: ReorderBody, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    for idx, cid in enumerate(body.ids, start=1):
        await db.menu_categories.update_one({"_id": _oid(cid), "restaurant_id": rid},
                                            {"$set": {"display_order": idx, "updated_at": now_iso()}})
    return {"message": "Ordre mis à jour"}


# ================= ITEMS =================
@router.get("/items")
async def list_items(category_id: Optional[str] = None, search: Optional[str] = None,
                     user: dict = Depends(VIEW)):
    rid = tenant_id_of(user)
    q = {"restaurant_id": rid}
    if category_id:
        q["category_id"] = category_id
    if search:
        q["name"] = {"$regex": search, "$options": "i"}
    docs = await db.menu_items.find(q).sort("display_order", 1).to_list(2000)
    return [serialize(d) for d in docs]


@router.get("/items/{item_id}")
async def get_item(item_id: str, user: dict = Depends(VIEW)):
    rid = tenant_id_of(user)
    doc = await db.menu_items.find_one({"_id": _oid(item_id), "restaurant_id": rid})
    if not doc:
        raise HTTPException(status_code=404, detail="Article introuvable")
    return serialize(doc)


@router.post("/items")
async def create_item(body: ItemCreate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    await _own_category(rid, body.category_id)
    groups = body.option_group_ids or []
    if groups:
        await _validate_option_groups(rid, groups)
    ts = now_iso()
    order = body.display_order if body.display_order is not None else \
        await _next_order(db.menu_items, rid, {"category_id": body.category_id})
    doc = {"restaurant_id": rid, "category_id": body.category_id, "name": body.name.strip(),
           "description": body.description or "", "image_url": body.image_url or "", "price": int(body.price),
           "active": body.active if body.active is not None else True,
           "available": body.available if body.available is not None else True,
           "display_order": order, "option_group_ids": groups,
           "pricing_rules": body.pricing_rules or {},
           "stock": body.stock, "sku": (body.sku or "").strip(),
           "created_at": ts, "updated_at": ts}
    res = await db.menu_items.insert_one(doc)
    doc["_id"] = res.inserted_id
    await _log(rid, user["_id"], "MENU_ITEM_CREATE", body.name)
    return serialize(doc)


@router.patch("/items/{item_id}")
async def update_item(item_id: str, body: ItemUpdate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    item = await db.menu_items.find_one({"_id": _oid(item_id), "restaurant_id": rid})
    if not item:
        raise HTTPException(status_code=404, detail="Article introuvable")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    # Stock: un null explicite remet le stock en illimité (exclude_none l'aurait supprimé).
    if "stock" in body.model_fields_set and body.stock is None:
        updates["stock"] = None
    if "category_id" in updates:
        await _own_category(rid, updates["category_id"])
    if "option_group_ids" in updates:
        await _validate_option_groups(rid, updates["option_group_ids"])
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    if "price" in updates:
        updates["price"] = int(updates["price"])
    if "sku" in updates:
        updates["sku"] = (updates["sku"] or "").strip()
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    updates["updated_at"] = now_iso()
    await db.menu_items.update_one({"_id": _oid(item_id)}, {"$set": updates})
    await _log(rid, user["_id"], "MENU_ITEM_UPDATE", f"{item_id}:{list(updates.keys())}")
    doc = await db.menu_items.find_one({"_id": _oid(item_id)})
    return serialize(doc)


@router.patch("/items/{item_id}/availability")
async def set_availability(item_id: str, body: AvailabilityUpdate, user: dict = Depends(VIEW)):
    rid = tenant_id_of(user)
    item = await db.menu_items.find_one({"_id": _oid(item_id), "restaurant_id": rid})
    if not item:
        raise HTTPException(status_code=404, detail="Article introuvable")
    await db.menu_items.update_one({"_id": _oid(item_id)},
                                   {"$set": {"available": body.available, "updated_at": now_iso()}})
    await _log(rid, user["_id"], "MENU_ITEM_AVAILABILITY", f"{item_id}:{body.available}")
    doc = await db.menu_items.find_one({"_id": _oid(item_id)})
    return serialize(doc)


@router.delete("/items/{item_id}")
async def delete_item(item_id: str, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    item = await db.menu_items.find_one({"_id": _oid(item_id), "restaurant_id": rid})
    if not item:
        raise HTTPException(status_code=404, detail="Article introuvable")
    await db.menu_items.delete_one({"_id": _oid(item_id)})
    await _log(rid, user["_id"], "MENU_ITEM_DELETE", item_id)
    return {"message": "Article supprimé"}


@router.post("/items/reorder")
async def reorder_items(body: ReorderBody, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    for idx, iid in enumerate(body.ids, start=1):
        await db.menu_items.update_one({"_id": _oid(iid), "restaurant_id": rid},
                                       {"$set": {"display_order": idx, "updated_at": now_iso()}})
    return {"message": "Ordre mis à jour"}


# ================= OPTION GROUPS =================
@router.get("/option-groups")
async def list_option_groups(user: dict = Depends(VIEW)):
    rid = tenant_id_of(user)
    groups, options = await asyncio.gather(
        db.menu_option_groups.find({"restaurant_id": rid}).sort("display_order", 1).to_list(500),
        db.menu_options.find({"restaurant_id": rid}).sort("display_order", 1).to_list(2000),
    )
    options_by_group = {}
    for option in options:
        options_by_group.setdefault(option.get("group_id"), []).append(option)
    result = []
    for g in groups:
        opts = options_by_group.get(str(g["_id"]), [])
        gs = serialize(g)
        gs["options"] = [serialize(o) for o in opts]
        result.append(gs)
    return result


@router.post("/option-groups")
async def create_option_group(body: OptionGroupCreate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    if body.max_selections < body.min_selections:
        raise HTTPException(status_code=400, detail="max_selections doit être ≥ min_selections")
    ts = now_iso()
    order = body.display_order if body.display_order is not None else await _next_order(db.menu_option_groups, rid)
    doc = {"restaurant_id": rid, "name": body.name.strip(), "description": body.description or "",
           "required": bool(body.required), "min_selections": body.min_selections,
           "max_selections": body.max_selections, "display_order": order,
           "active": body.active if body.active is not None else True, "created_at": ts, "updated_at": ts}
    res = await db.menu_option_groups.insert_one(doc)
    doc["_id"] = res.inserted_id
    await _log(rid, user["_id"], "MENU_OPTIONGROUP_CREATE", body.name)
    return serialize(doc)


@router.patch("/option-groups/{group_id}")
async def update_option_group(group_id: str, body: OptionGroupUpdate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    group = await db.menu_option_groups.find_one({"_id": _oid(group_id), "restaurant_id": rid})
    if not group:
        raise HTTPException(status_code=404, detail="Groupe d'options introuvable")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    new_min = updates.get("min_selections", group.get("min_selections", 0))
    new_max = updates.get("max_selections", group.get("max_selections", 1))
    if new_max < new_min:
        raise HTTPException(status_code=400, detail="max_selections doit être ≥ min_selections")
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    updates["updated_at"] = now_iso()
    await db.menu_option_groups.update_one({"_id": _oid(group_id)}, {"$set": updates})
    await _log(rid, user["_id"], "MENU_OPTIONGROUP_UPDATE", group_id)
    doc = await db.menu_option_groups.find_one({"_id": _oid(group_id)})
    return serialize(doc)


@router.delete("/option-groups/{group_id}")
async def delete_option_group(group_id: str, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    group = await db.menu_option_groups.find_one({"_id": _oid(group_id), "restaurant_id": rid})
    if not group:
        raise HTTPException(status_code=404, detail="Groupe d'options introuvable")
    # Detach from items and delete child options (no silent loss of items themselves)
    await db.menu_items.update_many({"restaurant_id": rid, "option_group_ids": group_id},
                                    {"$pull": {"option_group_ids": group_id}})
    await db.menu_options.delete_many({"restaurant_id": rid, "group_id": group_id})
    await db.menu_option_groups.delete_one({"_id": _oid(group_id)})
    await _log(rid, user["_id"], "MENU_OPTIONGROUP_DELETE", group_id)
    return {"message": "Groupe d'options supprimé"}


# ================= OPTIONS =================
@router.post("/option-groups/{group_id}/options")
async def create_option(group_id: str, body: OptionCreate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    group = await db.menu_option_groups.find_one({"_id": _oid(group_id), "restaurant_id": rid})
    if not group:
        raise HTTPException(status_code=404, detail="Groupe d'options introuvable")
    ts = now_iso()
    order = body.display_order if body.display_order is not None else \
        await _next_order(db.menu_options, rid, {"group_id": group_id})
    doc = {"restaurant_id": rid, "group_id": group_id, "name": body.name.strip(),
           "description": body.description or "", "price_delta": int(body.price_delta),
           "active": body.active if body.active is not None else True,
           "available": body.available if body.available is not None else True,
           "stock": body.stock,
           "display_order": order, "created_at": ts, "updated_at": ts}
    res = await db.menu_options.insert_one(doc)
    doc["_id"] = res.inserted_id
    await _log(rid, user["_id"], "MENU_OPTION_CREATE", body.name)
    return serialize(doc)


@router.patch("/options/{option_id}")
async def update_option(option_id: str, body: OptionUpdate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    opt = await db.menu_options.find_one({"_id": _oid(option_id), "restaurant_id": rid})
    if not opt:
        raise HTTPException(status_code=404, detail="Option introuvable")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    # Stock: un null explicite remet le stock de la variante en illimité.
    if "stock" in body.model_fields_set and body.stock is None:
        updates["stock"] = None
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    if "price_delta" in updates:
        updates["price_delta"] = int(updates["price_delta"])
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    updates["updated_at"] = now_iso()
    await db.menu_options.update_one({"_id": _oid(option_id)}, {"$set": updates})
    await _log(rid, user["_id"], "MENU_OPTION_UPDATE", option_id)
    doc = await db.menu_options.find_one({"_id": _oid(option_id)})
    return serialize(doc)


@router.delete("/options/{option_id}")
async def delete_option(option_id: str, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    opt = await db.menu_options.find_one({"_id": _oid(option_id), "restaurant_id": rid})
    if not opt:
        raise HTTPException(status_code=404, detail="Option introuvable")
    await db.menu_options.delete_one({"_id": _oid(option_id)})
    await _log(rid, user["_id"], "MENU_OPTION_DELETE", option_id)
    return {"message": "Option supprimée"}


# ================= VARIANTS (matrice de combinaisons) =================
def _variant_key(option_ids: List[str]) -> str:
    return "|".join(sorted(str(o) for o in option_ids or []))


async def _validate_item_options(rid: str, item: dict, option_ids: List[str]) -> None:
    if len(set(option_ids)) != len(option_ids):
        raise HTTPException(status_code=400, detail="Option dupliquée")
    attached = set(item.get("option_group_ids") or [])
    for oid in option_ids:
        opt = await db.menu_options.find_one({"_id": _oid(oid), "restaurant_id": rid})
        if not opt or opt.get("group_id") not in attached:
            raise HTTPException(status_code=400, detail="Option incompatible avec cet article")


def _serialize_variant(v: dict) -> dict:
    out = serialize(v)
    out["key"] = v.get("variant_key", "")
    out["in_stock"] = item_in_stock(v)
    return out


@router.get("/items/{item_id}/variants")
async def list_variants(item_id: str, user: dict = Depends(VIEW)):
    rid = tenant_id_of(user)
    item = await db.menu_items.find_one({"_id": _oid(item_id), "restaurant_id": rid})
    if not item:
        raise HTTPException(status_code=404, detail="Article introuvable")
    docs = await db.menu_variants.find({"restaurant_id": rid, "item_id": item_id}).to_list(2000)
    return [_serialize_variant(v) for v in docs]


@router.post("/items/{item_id}/variants")
async def upsert_variant(item_id: str, body: VariantCreate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    item = await db.menu_items.find_one({"_id": _oid(item_id), "restaurant_id": rid})
    if not item:
        raise HTTPException(status_code=404, detail="Article introuvable")
    await _validate_item_options(rid, item, body.option_ids)
    key = _variant_key(body.option_ids)
    ts = now_iso()
    data = {
        "restaurant_id": rid, "item_id": item_id, "variant_key": key,
        "option_ids": body.option_ids, "sku": (body.sku or "").strip(),
        "price_delta": int(body.price_delta or 0), "stock": body.stock,
        "active": body.active if body.active is not None else True, "updated_at": ts,
    }
    existing = await db.menu_variants.find_one({"restaurant_id": rid, "item_id": item_id, "variant_key": key})
    if existing:
        await db.menu_variants.update_one({"_id": existing["_id"]}, {"$set": data})
        doc = await db.menu_variants.find_one({"_id": existing["_id"]})
    else:
        data["created_at"] = ts
        res = await db.menu_variants.insert_one(data)
        doc = {**data, "_id": res.inserted_id}
    await _log(rid, user["_id"], "MENU_VARIANT_UPSERT", key)
    return _serialize_variant(doc)


@router.patch("/variants/{variant_id}")
async def update_variant(variant_id: str, body: VariantUpdate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    variant = await db.menu_variants.find_one({"_id": _oid(variant_id), "restaurant_id": rid})
    if not variant:
        raise HTTPException(status_code=404, detail="Variante introuvable")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "stock" in body.model_fields_set and body.stock is None:
        updates["stock"] = None
    if "option_ids" in updates:
        item = await db.menu_items.find_one({"_id": _oid(variant["item_id"], "article"), "restaurant_id": rid})
        if not item:
            raise HTTPException(status_code=404, detail="Article introuvable")
        await _validate_item_options(rid, item, updates["option_ids"])
        updates["variant_key"] = _variant_key(updates["option_ids"])
    if "sku" in updates:
        updates["sku"] = (updates["sku"] or "").strip()
    if "price_delta" in updates:
        updates["price_delta"] = int(updates["price_delta"])
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    updates["updated_at"] = now_iso()
    await db.menu_variants.update_one({"_id": variant["_id"]}, {"$set": updates})
    await _log(rid, user["_id"], "MENU_VARIANT_UPDATE", variant_id)
    doc = await db.menu_variants.find_one({"_id": variant["_id"]})
    return _serialize_variant(doc)


@router.delete("/variants/{variant_id}")
async def delete_variant(variant_id: str, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    variant = await db.menu_variants.find_one({"_id": _oid(variant_id), "restaurant_id": rid})
    if not variant:
        raise HTTPException(status_code=404, detail="Variante introuvable")
    await db.menu_variants.delete_one({"_id": variant["_id"]})
    await _log(rid, user["_id"], "MENU_VARIANT_DELETE", variant_id)
    return {"message": "Variante supprimée"}


# ================= PUBLIC CATALOG =================
@router.get("/public/{restaurant_public_id}")
async def public_catalog(restaurant_public_id: str):
    restaurant = await db.restaurants.find_one({"public_id": restaurant_public_id, "status": "active"})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant introuvable")
    rid = str(restaurant["_id"])

    # Fetch the public catalogue in parallel, avoiding one item query per category.
    categories, group_docs, option_docs, item_docs, variant_docs = await asyncio.gather(
        db.menu_categories.find({"restaurant_id": rid, "active": True}).sort("display_order", 1).to_list(500),
        db.menu_option_groups.find({"restaurant_id": rid, "active": True}).to_list(500),
        db.menu_options.find({"restaurant_id": rid, "active": True}).sort("display_order", 1).to_list(2000),
        db.menu_items.find({"restaurant_id": rid, "active": True}).sort("display_order", 1).to_list(2000),
        db.menu_variants.find({"restaurant_id": rid}).to_list(5000),
    )
    groups = {str(g["_id"]): g for g in group_docs}
    options_by_group = {}
    for o in option_docs:
        options_by_group.setdefault(o["group_id"], []).append(o)
    variants_by_item = {}
    for v in variant_docs:
        if v.get("active", True) is False:
            continue
        variants_by_item.setdefault(v.get("item_id"), []).append(v)
    items_by_category = {}
    for item in item_docs:
        items_by_category.setdefault(item.get("category_id"), []).append(item)

    out_categories = []
    for cat in categories:
        items = items_by_category.get(str(cat["_id"]), [])
        out_items = []
        for it in items:
            item_groups = []
            for gid in it.get("option_group_ids", []):
                g = groups.get(gid)
                if not g:
                    continue
                choices = [{
                    "id": str(o["_id"]), "name": o["name"], "price_delta": o.get("price_delta", 0),
                    "available": o.get("available", True), "in_stock": item_in_stock(o),
                } for o in options_by_group.get(gid, [])]
                item_groups.append({
                    "id": str(g["_id"]), "name": g["name"], "description": g.get("description", ""),
                    "required": g.get("required", False), "min": g.get("min_selections", 0),
                    "max": g.get("max_selections", 1), "choices": choices,
                })
            out_items.append({
                "id": str(it["_id"]), "name": it["name"], "description": it.get("description", ""),
                "image_url": it.get("image_url") or it.get("image", ""), "price": it.get("price", 0),
                "pricing_rules": it.get("pricing_rules") or {},
                "sku": it.get("sku", ""), "in_stock": item_in_stock(it),
                "variants": [{
                    "key": v.get("variant_key", ""),
                    "option_ids": v.get("option_ids") or [],
                    "sku": v.get("sku", ""),
                    "price_delta": v.get("price_delta", 0),
                    "in_stock": item_in_stock(v),
                } for v in variants_by_item.get(str(it["_id"]), [])],
                "available": it.get("available", True), "options": item_groups,
            })
        out_categories.append({"id": str(cat["_id"]), "name": cat["name"],
                               "description": cat.get("description", ""), "items": out_items})

    return {
        "restaurant": {"public_id": restaurant["public_id"], "name": restaurant["name"],
                       "secteur": restaurant.get("secteur", "restaurant"),
                       "currency": restaurant.get("currency", "FCFA"), "logo": restaurant.get("logo", "")},
        "categories": out_categories,
    }
