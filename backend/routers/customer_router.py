from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId

from database import db
from services import order_service as svc
from auth import require_roles, tenant_id_of
from models import serialize, RESTAURANT_OWNER, RESTAURANT_MANAGER

router = APIRouter(prefix="/customers", tags=["customers"])
MANAGE = require_roles(RESTAURANT_OWNER, RESTAURANT_MANAGER)


async def _stats_for(rid: str, customer_id: str) -> dict:
    orders = await db.orders.find({"restaurant_id": rid, "customer_id": customer_id}).to_list(2000)
    valid = [o for o in orders if o.get("status") != "CANCELLED"]
    total_spent = sum(o.get("total", 0) for o in valid)
    last = max((o.get("created_at", "") for o in orders), default=None)
    return {"orders_count": len(orders), "total_spent": total_spent, "last_order_at": last}


@router.get("")
async def list_customers(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                        search: str = Query("", max_length=100), user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    rows = await db.customers_page(rid, search, page, page_size)
    total = rows[0]["total_count"] if rows else 0
    return {"items": [serialize(row) for row in rows], "total": total,
            "page": page, "page_size": page_size}


@router.get("/{customer_id}")
async def customer_detail(customer_id: str, user: dict = Depends(MANAGE)):
    rid = tenant_id_of(user)
    try:
        c = await db.customers.find_one({"_id": ObjectId(customer_id), "restaurant_id": rid})
    except Exception:
        raise HTTPException(status_code=400, detail="Identifiant invalide")
    if not c:
        raise HTTPException(status_code=404, detail="Client introuvable")
    s = serialize(c)
    s.update(await _stats_for(rid, customer_id))
    orders = await db.orders.find({"restaurant_id": rid, "customer_id": customer_id}).sort("created_at", -1).to_list(500)
    s["orders"] = [serialize(o) for o in orders]
    return s
