"""D1.54 — Weekly menu planning (reference-only, no catalogue duplication).

One document per (restaurant, day) in `weekly_menus`:
    {restaurant_id, day, active, item_ids[], created_at, updated_at}
- `day` uses the same keys as restaurants.opening_hours (monday..sunday);
- `item_ids` is the presentation order; names/prices/images are NEVER copied
  (resolution always happens against menu_items at read time);
- the unique index (restaurant_id, day) added in seed.ensure_indexes makes a
  duplicate day impossible at the storage level;
- writes validate: known day, ids well-formed, ids belonging to THIS
  restaurant, no duplicates — a day PUT never mutates the catalogue.

Conventions shared with menu_router: MANAGE/VIEW roles, _oid validation and
per-tenant scoping (restaurant_id always comes from the session, never body).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db
from models import now_iso
from auth import tenant_id_of
from routers.menu_router import MANAGE, VIEW, _oid

router = APIRouter(prefix="/menu", tags=["weekly-menu"])

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_SET = set(DAYS)


class WeeklyDayUpdate(BaseModel):
    # item_ids absent -> only the active flag changes; [] clears the day.
    item_ids: Optional[List[str]] = None
    active: Optional[bool] = None


async def _audit(rid: str, uid, action: str, detail) -> None:
    await db.audit_logs.insert_one({"restaurant_id": rid, "user_id": uid, "action": action,
                                    "detail": str(detail), "created_at": now_iso()})


def _check_day(day: str) -> str:
    if day not in DAY_SET:
        raise HTTPException(status_code=400, detail=f"Jour invalide : {day}")
    return day


async def _validate_items(rid: str, item_ids: List[str]) -> List[str]:
    """Strict: every id must be well-formed, exist and belong to this tenant.
    Duplicates are refused (the model of the collection forbids them anyway)."""
    if len(set(item_ids)) != len(item_ids):
        raise HTTPException(status_code=400, detail="Doublon de produit dans le menu du jour.")
    for iid in item_ids:
        item = await db.menu_items.find_one({"_id": _oid(iid, "produit"), "restaurant_id": rid})
        if not item:
            raise HTTPException(status_code=400, detail="Article introuvable pour ce restaurant")
    return list(item_ids)


async def _resolve_items(rid: str, item_ids: List[str]) -> list:
    """Read-time resolution against the catalogue. Items deleted since their
    planning are silently skipped (the plan keeps the raw id until rewritten)."""
    out = []
    for iid in item_ids:
        try:
            _id = ObjectId(iid)
        except Exception:
            continue
        it = await db.menu_items.find_one({"_id": _id, "restaurant_id": rid})
        if not it:
            continue
        out.append({"id": str(it["_id"]), "name": it.get("name", ""),
                    "price": it.get("price", 0),
                    "image_url": it.get("image_url") or it.get("image", ""),
                    "available": it.get("available", True),
                    "active": it.get("active", True)})
    return out


async def _day_payload(rid: str, day: str, doc: Optional[dict]) -> dict:
    if not doc:
        return {"day": day, "configured": False, "active": False,
                "item_ids": [], "items": []}
    item_ids = list(doc.get("item_ids", []))
    return {"day": day, "configured": True, "active": bool(doc.get("active", True)),
            "item_ids": item_ids, "items": await _resolve_items(rid, item_ids)}


@router.get("/weekly")
async def list_weekly(user: dict = Depends(VIEW)):
    rid = tenant_id_of(user)
    docs = await db.weekly_menus.find({"restaurant_id": rid}).to_list(100)
    by_day = {d.get("day"): d for d in docs if d.get("day") in DAY_SET}
    days = [await _day_payload(rid, day, by_day.get(day)) for day in DAYS]
    return {"days": days}


@router.put("/weekly/{day}")
async def upsert_weekly_day(day: str, body: WeeklyDayUpdate, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    _check_day(day)
    if body.item_ids is None and body.active is None:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    doc = await db.weekly_menus.find_one({"restaurant_id": rid, "day": day})
    updates = {}
    if body.item_ids is not None:
        updates["item_ids"] = await _validate_items(rid, body.item_ids)
    if body.active is not None:
        updates["active"] = bool(body.active)
    ts = now_iso()
    if doc is None:
        if body.item_ids is None:
            raise HTTPException(status_code=400, detail="Aucun menu configuré pour ce jour")
        doc = {"restaurant_id": rid, "day": day, "active": updates.get("active", True),
               "item_ids": updates["item_ids"], "created_at": ts, "updated_at": ts}
        await db.weekly_menus.insert_one(doc)
    else:
        updates["updated_at"] = ts
        await db.weekly_menus.update_one({"_id": doc["_id"]}, {"$set": updates})
        doc.update(updates)
    await _audit(rid, user["_id"], "WEEKLY_MENU_UPDATE",
                 f"{day}:{len(doc.get('item_ids', []))} produit(s), active={doc.get('active')}")
    return await _day_payload(rid, day, doc)


@router.post("/weekly/{day}/copy-from/{source_day}")
async def copy_weekly_day(day: str, source_day: str, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    _check_day(day)
    _check_day(source_day)
    src = await db.weekly_menus.find_one({"restaurant_id": rid, "day": source_day})
    if not src:
        raise HTTPException(status_code=400, detail="Le jour source n'a pas de menu configuré")
    # Copy is a server-side read: unknown ids are dropped (items deleted since
    # the source was written), duplicates are removed, order is preserved.
    seen, item_ids = set(), []
    for iid in src.get("item_ids", []):
        if iid in seen:
            continue
        seen.add(iid)
        item_ids.append(iid)
    resolved_ids = [p["id"] for p in await _resolve_items(rid, item_ids)]
    ts = now_iso()
    doc = await db.weekly_menus.find_one({"restaurant_id": rid, "day": day})
    if doc is None:
        doc = {"restaurant_id": rid, "day": day, "active": bool(src.get("active", True)),
               "item_ids": resolved_ids, "created_at": ts, "updated_at": ts}
        await db.weekly_menus.insert_one(doc)
    else:
        doc.update({"item_ids": resolved_ids, "active": bool(src.get("active", True)),
                    "updated_at": ts})
        await db.weekly_menus.update_one({"_id": doc["_id"]},
                                         {"$set": {"item_ids": resolved_ids,
                                                   "active": doc["active"],
                                                   "updated_at": ts}})
    await _audit(rid, user["_id"], "WEEKLY_MENU_COPY", f"{source_day}->{day}:{len(resolved_ids)} produit(s)")
    return await _day_payload(rid, day, doc)


@router.delete("/weekly/{day}")
async def delete_weekly_day(day: str, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    _check_day(day)
    doc = await db.weekly_menus.find_one({"restaurant_id": rid, "day": day})
    if not doc:
        raise HTTPException(status_code=404, detail="Menu non configuré pour ce jour")
    await db.weekly_menus.delete_one({"_id": doc["_id"]})
    await _audit(rid, user["_id"], "WEEKLY_MENU_DELETE", day)
    return {"message": "Menu du jour supprimé"}
