from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import db
from services import order_service as svc

router = APIRouter(prefix="/public", tags=["public-cart"])


class CreateCartBody(BaseModel):
    restaurant_public_id: str


class AddItemBody(BaseModel):
    item_id: str
    quantity: int = Field(ge=1)
    option_ids: Optional[List[str]] = []


class UpdateItemBody(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=1)
    option_ids: Optional[List[str]] = None


@router.get("/menu/{restaurant_public_id}")
async def public_menu(restaurant_public_id: str):
    r = await svc.get_restaurant_by_public_id(db, restaurant_public_id)
    data = await svc.get_available_menu(db, str(r["_id"]))
    data["restaurant"]["currency"] = r.get("currency", "FCFA")
    data["restaurant"]["logo"] = r.get("logo", "")
    data["restaurant"]["welcome_message"] = r.get("widget", {}).get("welcome_message", "")
    # D1.50: widget theming for the public menu — same pattern as welcome_message,
    # only the public widget config is read, never private restaurant fields.
    data["restaurant"]["primary_color"] = r.get("widget", {}).get("primary_color", "")
    return data


@router.get("/delivery-zones/{restaurant_public_id}")
async def public_zones(restaurant_public_id: str):
    r = await svc.get_restaurant_by_public_id(db, restaurant_public_id)
    return await svc.get_delivery_zones(db, str(r["_id"]), active_only=True)


@router.post("/cart")
async def create_cart(body: CreateCartBody):
    r = await svc.get_restaurant_by_public_id(db, body.restaurant_public_id)
    cart = await svc.create_cart(db, str(r["_id"]))
    return {"cart_id": cart["cart_id"], "restaurant_id": str(r["_id"])}


@router.get("/cart/{cart_id}")
async def get_cart(cart_id: str):
    cart = await svc.get_cart(db, cart_id)
    view = await svc.calculate_cart(db, cart["restaurant_id"], cart)
    return {"cart_id": cart_id, "restaurant_id": cart["restaurant_id"], "status": cart["status"], **view}


@router.post("/cart/{cart_id}/items")
async def add_item(cart_id: str, body: AddItemBody):
    cart = await svc.get_cart(db, cart_id)
    cart = await svc.add_to_cart(db, cart["restaurant_id"], cart, body.item_id, body.quantity, body.option_ids or [])
    view = await svc.calculate_cart(db, cart["restaurant_id"], cart)
    return {"cart_id": cart_id, "restaurant_id": cart["restaurant_id"], "status": cart["status"], **view}


@router.patch("/cart/{cart_id}/items/{cart_item_id}")
async def update_item(cart_id: str, cart_item_id: str, body: UpdateItemBody):
    cart = await svc.get_cart(db, cart_id)
    cart = await svc.update_cart_item(db, cart["restaurant_id"], cart, cart_item_id, body.quantity, body.option_ids)
    view = await svc.calculate_cart(db, cart["restaurant_id"], cart)
    return {"cart_id": cart_id, "restaurant_id": cart["restaurant_id"], "status": cart["status"], **view}


@router.delete("/cart/{cart_id}/items/{cart_item_id}")
async def remove_item(cart_id: str, cart_item_id: str):
    cart = await svc.get_cart(db, cart_id)
    cart = await svc.remove_cart_item(db, cart, cart_item_id)
    view = await svc.calculate_cart(db, cart["restaurant_id"], cart)
    return {"cart_id": cart_id, "restaurant_id": cart["restaurant_id"], "status": cart["status"], **view}


@router.delete("/cart/{cart_id}")
async def clear_cart(cart_id: str):
    cart = await svc.get_cart(db, cart_id)
    await svc.clear_cart(db, cart)
    return {"message": "Panier vidé"}


@router.post("/cart/{cart_id}/validate")
async def validate_cart(cart_id: str):
    cart = await svc.get_cart(db, cart_id)
    return await svc.validate_cart(db, cart["restaurant_id"], cart)
