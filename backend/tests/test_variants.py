"""Matrice de variantes — clé, prix, recherche et stock par combinaison."""
import asyncio

from bson import ObjectId

from services import order_service as svc


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, q):
        for doc in self.docs:
            ok = True
            for key, value in q.items():
                if isinstance(value, dict) and "$ne" in value:
                    if doc.get(key) == value["$ne"]:
                        ok = False
                        break
                elif doc.get(key) != value:
                    ok = False
                    break
            if ok:
                return doc
        return None

    async def update_one(self, q, update):
        doc = await self.find_one(q)
        if doc and "$set" in update:
            doc.update(update["$set"])


class FakeDB:
    def __init__(self, variants=None, items=None):
        self.menu_variants = FakeCollection(variants)
        self.menu_items = FakeCollection(items)
        self.pool = None


def _run(coro):
    return asyncio.run(coro)


def _variant(option_ids=("a", "b"), stock=None, active=True, price_delta=0):
    doc = {
        "_id": ObjectId(), "restaurant_id": "rest-1", "item_id": "item-1",
        "variant_key": svc.variant_key(option_ids), "option_ids": list(option_ids),
        "price_delta": price_delta, "sku": "SKU-1", "active": active,
    }
    if stock is not None:
        doc["stock"] = stock
    return doc


def test_variant_key_is_order_independent():
    assert svc.variant_key(["b", "a"]) == svc.variant_key(["a", "b"])
    assert svc.variant_key([]) == ""
    assert svc.variant_key(None) == ""


def test_line_price_includes_variant_delta():
    assert svc.line_unit_price({"price": 10000}, {}, {"price_delta": 1500}) == 11500


def test_line_price_variant_plus_distance():
    item = {"price": 1000, "pricing_rules": {"per_km": 500}}
    assert svc.line_unit_price(item, {"distance_km": 2}, {"price_delta": 200}) == 2200


def test_find_variant_matches_sorted_key():
    variant = _variant(option_ids=("b", "a"))
    db = FakeDB([variant])
    assert _run(svc._find_variant(db, "rest-1", "item-1", ["a", "b"])) is variant


def test_find_variant_ignores_inactive():
    variant = _variant(active=False)
    db = FakeDB([variant])
    assert _run(svc._find_variant(db, "rest-1", "item-1", ["a", "b"])) is None


def test_find_variant_requires_options():
    db = FakeDB([_variant()])
    assert _run(svc._find_variant(db, "rest-1", "item-1", [])) is None


def test_find_variant_without_collection_is_safe():
    class NoVariants:
        pool = None

    assert _run(svc._find_variant(NoVariants(), "rest-1", "item-1", ["a", "b"])) is None


def test_reserve_variant_stock():
    variant = _variant(stock=2)
    db = FakeDB([variant])
    assert _run(svc._reserve_stock(db, "rest-1", str(variant["_id"]), 1, collection="menu_variants")) is True
    assert variant["stock"] == 1
    assert _run(svc._reserve_stock(db, "rest-1", str(variant["_id"]), 2, collection="menu_variants")) is False


def test_restore_order_stock_restores_variant():
    variant = _variant(stock=0)
    db = FakeDB([variant])
    order = {"stock_reserved": True, "items": [
        {"item_id": str(ObjectId()), "quantity": 2, "variant_id": str(variant["_id"])},
    ]}
    _run(svc._restore_order_stock(db, "rest-1", order))
    assert variant["stock"] == 2
