from fastapi import APIRouter, Depends
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from database import db
from auth import get_current_user, tenant_id_of

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    rid = tenant_id_of(user)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=7)).isoformat()

    orders = await db.orders.find({"restaurant_id": rid}).to_list(5000)
    today_orders = [o for o in orders if str(o.get("created_at", "")).startswith(today)]
    week_orders = [o for o in orders if str(o.get("created_at", "")) >= week_start]
    non_cancelled = [o for o in orders if o.get("status") != "CANCELLED"]

    revenue_today = sum(o.get("total", 0) for o in today_orders if o.get("status") != "CANCELLED")
    revenue_week = sum(o.get("total", 0) for o in week_orders if o.get("status") != "CANCELLED")
    revenue_total = sum(o.get("total", 0) for o in non_cancelled)
    pending = len([o for o in orders if o.get("status") == "PENDING"])
    preparing = len([o for o in orders if o.get("status") == "PREPARING"])
    ready = len([o for o in orders if o.get("status") == "READY"])
    completed_today = len([o for o in today_orders if o.get("status") == "DELIVERED"])
    avg_basket = round(revenue_total / len(non_cancelled)) if non_cancelled else 0

    menu_items = await db.menu_items.count_documents({"restaurant_id": rid})
    customers = await db.customers.count_documents({"restaurant_id": rid})
    users_count = await db.users.count_documents({"restaurant_id": rid})

    return {
        "orders_today": len(today_orders),
        "orders_week": len(week_orders),
        "revenue_today": revenue_today,
        "revenue_week": revenue_week,
        "pending": pending,
        "preparing": preparing,
        "ready": ready,
        "completed_today": completed_today,
        "avg_basket": avg_basket,
        "total_orders": len(orders),
        "menu_items": menu_items,
        "customers": customers,
        "users": users_count,
    }
