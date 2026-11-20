"""P2 e-commerce — stock : helpers, réservation atomique et restitution."""
import pytest
from bson import ObjectId

from services import order_service as svc


class FakeMenuItems:
    def __init__(self, items):
        self.items = items

    async def find_one(self, q):
        for item in self.items:
            if str(item["_id"]) != str(q.get("_id")):
                continue
            if "restaurant_id" in q and item.get("restaurant_id") != q["restaurant_id"]:
                continue
            return item
        return None

    async def update_one(self, q, update):
        item = await self.find_one(q)
        if item and "$set" in update:
            item.update(update["$set"])


class FakeDB:
    def __init__(self, items=None, options=None):
        self.menu_items = FakeMenuItems(items or [])
        self.menu_options = FakeMenuItems(options or [])
        self.pool = None


def _item(stock=None, **extra):
    doc = {"_id": ObjectId(), "restaurant_id": "rest-1", "name": "Produit", "price": 1000}
    if stock is not None:
        doc["stock"] = stock
    doc.update(extra)
    return doc


def _option(stock=None, **extra):
    doc = {"_id": ObjectId(), "restaurant_id": "rest-1", "name": "Taille M", "price_delta": 0}
    if stock is not None:
        doc["stock"] = stock
    doc.update(extra)
    return doc


def test_stock_of_unlimited_and_finite():
    assert svc._stock_of({}) is None
    assert svc._stock_of({"stock": None}) is None
    assert svc._stock_of({"stock": 5}) == 5
    assert svc._stock_of({"stock": "7"}) == 7
    assert svc._stock_of({"stock": "abc"}) == 0


def test_item_in_stock():
    assert svc.item_in_stock({}) is True
    assert svc.item_in_stock({"stock": None}) is True
    assert svc.item_in_stock({"stock": 0}) is False
    assert svc.item_in_stock({"stock": 2}) is True


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_reserve_stock_decrements_and_rejects():
    item = _item(stock=3)
    db = FakeDB([item])

    assert _run(svc._reserve_stock(db, "rest-1", str(item["_id"]), 2)) is True
    assert item["stock"] == 1

    assert _run(svc._reserve_stock(db, "rest-1", str(item["_id"]), 2)) is False
    assert item["stock"] == 1

    assert _run(svc._reserve_stock(db, "rest-1", str(item["_id"]), 1)) is True
    assert item["stock"] == 0


def test_reserve_unlimited_is_a_noop():
    item = _item(stock=None)
    db = FakeDB([item])
    assert _run(svc._reserve_stock(db, "rest-1", str(item["_id"]), 10)) is True
    assert "stock" not in item


def test_reserve_unknown_item_fails():
    db = FakeDB([])
    assert _run(svc._reserve_stock(db, "rest-1", str(ObjectId()), 1)) is False


def test_restore_stock_adds_back():
    item = _item(stock=0)
    db = FakeDB([item])
    _run(svc._restore_stock(db, "rest-1", str(item["_id"]), 3))
    assert item["stock"] == 3


def test_restore_order_stock_sums_lines():
    item = _item(stock=0)
    db = FakeDB([item])
    order = {"stock_reserved": True, "items": [
        {"item_id": str(item["_id"]), "quantity": 1},
        {"item_id": str(item["_id"]), "quantity": 2},
    ]}
    _run(svc._restore_order_stock(db, "rest-1", order))
    assert item["stock"] == 3


def test_restore_order_stock_ignores_unlimited():
    item = _item(stock=None)
    db = FakeDB([item])
    order = {"stock_reserved": True, "items": [{"item_id": str(item["_id"]), "quantity": 2}]}
    _run(svc._restore_order_stock(db, "rest-1", order))
    assert "stock" not in item


def test_restore_order_stock_skips_unmarked_orders():
    item = _item(stock=0)
    db = FakeDB([item])
    order = {"items": [{"item_id": str(item["_id"]), "quantity": 2}]}
    _run(svc._restore_order_stock(db, "rest-1", order))
    assert item["stock"] == 0


def test_reserve_option_stock():
    opt = _option(stock=2)
    db = FakeDB(options=[opt])

    assert _run(svc._reserve_stock(db, "rest-1", str(opt["_id"]), 1, collection="menu_options")) is True
    assert opt["stock"] == 1

    assert _run(svc._reserve_stock(db, "rest-1", str(opt["_id"]), 2, collection="menu_options")) is False
    assert opt["stock"] == 1


def test_restore_order_stock_restores_variants():
    item = _item(stock=0)
    opt = _option(stock=0)
    db = FakeDB([item], [opt])
    order = {"stock_reserved": True, "items": [
        {"item_id": str(item["_id"]), "quantity": 2, "options": [{"option_id": str(opt["_id"])}]},
    ]}
    _run(svc._restore_order_stock(db, "rest-1", order))
    assert item["stock"] == 2
    assert opt["stock"] == 2


def test_invalid_stock_collection_rejected():
    db = FakeDB()
    with pytest.raises(ValueError):
        _run(svc._reserve_stock(db, "rest-1", str(ObjectId()), 1, collection="users"))
