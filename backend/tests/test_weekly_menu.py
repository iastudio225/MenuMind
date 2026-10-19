"""D1.54 étape 1 — weekly menu planning (mocked db, no network, no real DB).

Covers: seven-day defaults, upsert + audit, strict validation (day, malformed
id, unknown item, foreign item, duplicates), active-only toggle, tenant
isolation, copy-from semantics (order, deleted items dropped, source kept),
delete without touching the catalogue, and the role wiring actually used by
the routes (MANAGE/VIEW from menu_router).
"""
import os

# routers -> database reads MONGO_URL/DB_NAME at import time. The Mongo client
# is lazy (no network call, no real credentials): unit tests stay offline.
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017/restoia-unit")
os.environ.setdefault("DB_NAME", "restoia-unit")

import copy
import inspect

import pytest
from bson import ObjectId
from fastapi import HTTPException

from routers import weekly_menu_router as wm


def run(coro):
    import asyncio
    return asyncio.run(coro)


# =============== Fakes ===============
class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *args, **kwargs):
        return self

    async def to_list(self, length=None):
        return [dict(d) for d in self._docs[:length]]


class FakeCol:
    def __init__(self):
        self.docs = []
        self._n = 0

    @staticmethod
    def _matches(doc, query):
        return all(doc.get(k) == v for k, v in query.items())

    async def find_one(self, query):
        for d in self.docs:
            if self._matches(d, query):
                return d
        return None

    def find(self, query):
        return FakeCursor([d for d in self.docs if self._matches(d, query)])

    async def insert_one(self, doc):
        self._n += 1
        doc.setdefault("_id", f"oid-{self._n}")
        self.docs.append(doc)

    async def update_one(self, query, update):
        doc = await self.find_one(query)
        if doc and "$set" in update:
            doc.update(update["$set"])

    async def delete_one(self, query):
        doc = await self.find_one(query)
        if doc:
            self.docs.remove(doc)


class FakeDB:
    def __init__(self):
        self.restaurants = FakeCol()
        self.weekly_menus = FakeCol()
        self.menu_items = FakeCol()
        # Read by order_service.get_available_menu (day-menu resolution):
        self.menu_categories = FakeCol()
        self.menu_option_groups = FakeCol()
        self.menu_options = FakeCol()
        self.audit_logs = FakeCol()


OWNER_A = {"_id": "u-a", "role": "RESTAURANT_OWNER", "restaurant_id": "rest-A"}
OWNER_B = {"_id": "u-b", "role": "RESTAURANT_OWNER", "restaurant_id": "rest-B"}
STAFF_A = {"_id": "u-s", "role": "RESTAURANT_STAFF", "restaurant_id": "rest-A"}


@pytest.fixture
def env(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(wm, "db", db)
    return db


def add_item(db, rid, name, price=1000, available=True, active=True,
             image_url=None, legacy_image=None):
    doc = {"_id": ObjectId(), "restaurant_id": rid, "category_id": "cat-1",
           "name": name, "description": "", "price": price, "active": active,
           "available": available, "display_order": 1, "option_group_ids": [],
           "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z"}
    doc["image_url"] = image_url if image_url is not None else ""
    if legacy_image is not None:
        doc["image"] = legacy_image
    db.menu_items.docs.append(doc)
    return doc


def audit_actions(db):
    return [d["action"] for d in db.audit_logs.docs]


# =============== 1. GET defaults ===============
def test_get_returns_seven_days_in_order(env):
    out = run(wm.list_weekly(user=OWNER_A))
    assert [d["day"] for d in out["days"]] == wm.DAYS
    assert all(d["configured"] is False and d["item_ids"] == [] and d["items"] == []
               for d in out["days"])


# =============== 2. PUT creates + resolves + audits ===============
def test_put_creates_day_and_resolves_items(env):
    p1 = add_item(env, "rest-A", "Poulet braisé", price=5000, image_url="https://img/1.jpg")
    p2 = add_item(env, "rest-A", "Eau", price=500, legacy_image="https://img/2.jpg")
    out = run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(p1["_id"]), str(p2["_id"])]),
                                   user=OWNER_A))
    assert out["configured"] is True and out["active"] is True
    assert out["item_ids"] == [str(p1["_id"]), str(p2["_id"])]
    assert [i["name"] for i in out["items"]] == ["Poulet braisé", "Eau"]
    assert out["items"][0]["price"] == 5000
    assert out["items"][0]["image_url"] == "https://img/1.jpg"
    assert out["items"][1]["image_url"] == "https://img/2.jpg"  # legacy fallback
    assert out["items"][0]["available"] is True
    assert audit_actions(env) == ["WEEKLY_MENU_UPDATE"]
    # GET reflects the same state
    got = run(wm.list_weekly(user=OWNER_A))
    monday = next(d for d in got["days"] if d["day"] == "monday")
    assert monday["configured"] is True and len(monday["items"]) == 2


def test_put_empty_item_ids_configures_empty_day(env):
    out = run(wm.upsert_weekly_day("sunday", wm.WeeklyDayUpdate(item_ids=[]), user=OWNER_A))
    assert out["configured"] is True and out["item_ids"] == [] and out["items"] == []


def test_put_response_includes_availability_and_inactive_flags(env):
    p = add_item(env, "rest-A", "Poisson", available=False, active=False)
    out = run(wm.upsert_weekly_day("tuesday", wm.WeeklyDayUpdate(item_ids=[str(p["_id"])]), user=OWNER_A))
    assert out["items"][0]["available"] is False
    assert out["items"][0]["active"] is False


# =============== 3. Validation ===============
def test_put_invalid_day_rejected(env):
    with pytest.raises(HTTPException) as e:
        run(wm.upsert_weekly_day("lundi", wm.WeeklyDayUpdate(item_ids=[]), user=OWNER_A))
    assert e.value.status_code == 400


def test_put_malformed_id_rejected(env):
    with pytest.raises(HTTPException) as e:
        run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=["not-an-oid"]), user=OWNER_A))
    assert e.value.status_code == 400
    assert "invalide" in str(e.value.detail)
    assert env.weekly_menus.docs == []  # nothing written


def test_put_unknown_item_rejected(env):
    ghost = str(ObjectId())
    with pytest.raises(HTTPException) as e:
        run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[ghost]), user=OWNER_A))
    assert e.value.status_code == 400
    assert "introuvable" in str(e.value.detail)
    assert env.weekly_menus.docs == []


def test_put_foreign_item_rejected(env):
    foreign = add_item(env, "rest-B", "Plat de B")
    with pytest.raises(HTTPException) as e:
        run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(foreign["_id"])]), user=OWNER_A))
    assert e.value.status_code == 400
    assert "introuvable" in str(e.value.detail)  # no cross-tenant disclosure
    assert env.weekly_menus.docs == []


def test_put_duplicates_rejected(env):
    p = add_item(env, "rest-A", "Poulet")
    with pytest.raises(HTTPException) as e:
        run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(p["_id"]), str(p["_id"])]),
                                 user=OWNER_A))
    assert e.value.status_code == 400
    assert "Doublon" in str(e.value.detail)
    assert env.weekly_menus.docs == []


def test_put_active_only_on_configured_day_preserves_items(env):
    p = add_item(env, "rest-A", "Poulet")
    run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(p["_id"])]), user=OWNER_A))
    out = run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(active=False), user=OWNER_A))
    assert out["active"] is False
    assert out["item_ids"] == [str(p["_id"])]


def test_put_active_only_without_existing_day_rejected(env):
    with pytest.raises(HTTPException) as e:
        run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(active=True), user=OWNER_A))
    assert e.value.status_code == 400


def test_put_empty_body_rejected(env):
    with pytest.raises(HTTPException) as e:
        run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(), user=OWNER_A))
    assert e.value.status_code == 400
    assert "Aucune donnée" in str(e.value.detail)


# =============== 4. Tenant isolation ===============
def test_isolation_between_restaurants(env):
    a1 = add_item(env, "rest-A", "Plat A")
    b1 = add_item(env, "rest-B", "Plat B")
    run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(a1["_id"])]), user=OWNER_A))
    run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(b1["_id"])]), user=OWNER_B))
    assert len(env.weekly_menus.docs) == 2  # same day, one doc per restaurant

    got_a = next(d for d in run(wm.list_weekly(user=OWNER_A))["days"] if d["day"] == "monday")
    got_b = next(d for d in run(wm.list_weekly(user=OWNER_B))["days"] if d["day"] == "monday")
    assert [i["name"] for i in got_a["items"]] == ["Plat A"]
    assert [i["name"] for i in got_b["items"]] == ["Plat B"]


# =============== 5. Copy ===============
def test_copy_copies_order_and_active_flag(env):
    p1 = add_item(env, "rest-A", "Un")
    p2 = add_item(env, "rest-A", "Deux")
    run(wm.upsert_weekly_day("wednesday", wm.WeeklyDayUpdate(item_ids=[str(p2["_id"]), str(p1["_id"])]),
                             user=OWNER_A))
    out = run(wm.copy_weekly_day("friday", "wednesday", user=OWNER_A))
    assert out["configured"] is True and out["active"] is True
    assert out["item_ids"] == [str(p2["_id"]), str(p1["_id"])]  # order preserved
    # source untouched
    src = next(d for d in run(wm.list_weekly(user=OWNER_A))["days"] if d["day"] == "wednesday")
    assert src["item_ids"] == [str(p2["_id"]), str(p1["_id"])]
    assert audit_actions(env)[-1] == "WEEKLY_MENU_COPY"


def test_copy_from_unconfigured_day_rejected(env):
    with pytest.raises(HTTPException) as e:
        run(wm.copy_weekly_day("friday", "saturday", user=OWNER_A))
    assert e.value.status_code == 400
    assert "source" in str(e.value.detail)


def test_copy_invalid_day_rejected(env):
    with pytest.raises(HTTPException) as e:
        run(wm.copy_weekly_day("lundi", "monday", user=OWNER_A))
    assert e.value.status_code == 400


def test_copy_drops_items_deleted_since_source(env):
    p1 = add_item(env, "rest-A", "Vivant")
    p2 = add_item(env, "rest-A", "À supprimer")
    run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(p1["_id"]), str(p2["_id"])]),
                             user=OWNER_A))
    env.menu_items.docs.remove(p2)  # catalogue deleted after planning
    out = run(wm.copy_weekly_day("tuesday", "monday", user=OWNER_A))
    assert out["item_ids"] == [str(p1["_id"])]
    assert [i["name"] for i in out["items"]] == ["Vivant"]


def test_read_skips_deleted_items_but_keeps_raw_ids(env):
    p1 = add_item(env, "rest-A", "Restant")
    p2 = add_item(env, "rest-A", "Parti")
    run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(p1["_id"]), str(p2["_id"])]),
                             user=OWNER_A))
    env.menu_items.docs.remove(p2)
    got = next(d for d in run(wm.list_weekly(user=OWNER_A))["days"] if d["day"] == "monday")
    assert len(got["item_ids"]) == 2          # plan still holds the id
    assert [i["name"] for i in got["items"]] == ["Restant"]  # display skips it


# =============== 6. Delete ===============
def test_delete_clears_day_and_catalog_is_untouched(env):
    p = add_item(env, "rest-A", "Poulet")
    before = copy.deepcopy(env.menu_items.docs)
    run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(p["_id"])]), user=OWNER_A))
    res = run(wm.delete_weekly_day("monday", user=OWNER_A))
    assert "supprimé" in res["message"]
    got = next(d for d in run(wm.list_weekly(user=OWNER_A))["days"] if d["day"] == "monday")
    assert got["configured"] is False
    assert env.menu_items.docs == before  # catalogue NEVER mutated
    assert audit_actions(env)[-1] == "WEEKLY_MENU_DELETE"


def test_delete_unconfigured_day_rejected(env):
    with pytest.raises(HTTPException) as e:
        run(wm.delete_weekly_day("monday", user=OWNER_A))
    assert e.value.status_code == 404


def test_delete_is_tenant_scoped(env):
    p = add_item(env, "rest-A", "Plat A")
    run(wm.upsert_weekly_day("monday", wm.WeeklyDayUpdate(item_ids=[str(p["_id"])]), user=OWNER_A))
    with pytest.raises(HTTPException) as e:
        run(wm.delete_weekly_day("monday", user=OWNER_B))  # B has no monday doc
    assert e.value.status_code == 404
    assert len(env.weekly_menus.docs) == 1  # A's plan survives


# =============== 7. Roles / wiring ===============
def test_routes_are_wired_to_view_and_manage():
    assert inspect.signature(wm.list_weekly).parameters["user"].default.dependency is wm.VIEW
    assert inspect.signature(wm.upsert_weekly_day).parameters["user"].default.dependency is wm.MANAGE
    assert inspect.signature(wm.copy_weekly_day).parameters["user"].default.dependency is wm.MANAGE
    assert inspect.signature(wm.delete_weekly_day).parameters["user"].default.dependency is wm.MANAGE


def test_manage_refuses_staff_and_accepts_owner():
    with pytest.raises(HTTPException) as e:
        run(wm.MANAGE(user=STAFF_A))
    assert e.value.status_code == 403
    assert run(wm.MANAGE(user=OWNER_A)) is OWNER_A  # owner passes


def test_view_allows_staff():
    assert run(wm.VIEW(user=STAFF_A)) is STAFF_A


def test_tenant_id_required():
    with pytest.raises(HTTPException) as e:
        run(wm.list_weekly(user={"_id": "u-x", "role": "RESTAURANT_OWNER"}))
    assert e.value.status_code == 400
