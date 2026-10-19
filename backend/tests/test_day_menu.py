"""D1.54 étape 2 — day-menu helper (mocked db, no network, no paid AI call).

Covers the 15 mandated cases: active monday, all seven days, Africa/Abidjan,
another zone where the UTC day differs, near-midnight local rollover (both
directions), missing/empty timezone, invalid timezone (documented fallback),
no menu configured, configured-but-inactive, deleted product, inactive
product, unavailable product (real flag preserved), tenant isolation (incl.
a poisoned doc written around the router), item_ids order and an empty menu.

Deterministic instants only (2026-10-19 is a monday): no real MongoDB, no
network, no machine-timezone dependence — `now` is injected everywhere except
the one now=None path, which is clock-independent by planning all 7 days.
"""
import os

# routers -> database reads MONGO_URL/DB_NAME at import time. The Mongo client
# is lazy (no network call, no real credentials): unit tests stay offline.
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017/restoia-unit")
os.environ.setdefault("DB_NAME", "restoia-unit")

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from routers import weekly_menu_router as wm
from services import order_service as osvc
from tests.test_weekly_menu import FakeDB, add_item, run

UTC = timezone.utc
MON_NOON = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)       # lundi midi UTC
MON_LATE = datetime(2026, 10, 19, 23, 30, tzinfo=UTC)      # lundi 23:30 UTC
TUE_0000 = datetime(2026, 10, 20, 0, 0, tzinfo=UTC)        # bascule à minuit UTC
TOKYO_0030 = datetime(2026, 10, 19, 15, 30, tzinfo=UTC)    # = mar. 00:30 JST (mardi)
NY_2200 = datetime(2026, 10, 20, 2, 0, tzinfo=UTC)         # = lun. 22:00 EDT (lundi)
WEEK_NOONS = [datetime(2026, 10, d, 12, 0, tzinfo=UTC) for d in range(19, 26)]


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(wm, "db", fake)  # router writes land in the same fake
    return fake


def add_restaurant(db, tz="Africa/Abidjan", public_id=None):
    """tz=None omits the field entirely; tz="" leaves it empty."""
    oid = ObjectId()
    doc = {"_id": oid, "public_id": public_id or f"pub-{oid}",
           "name": "Chez Test", "status": "active"}
    if tz is not None:
        doc["timezone"] = tz
    db.restaurants.docs.append(doc)
    return str(oid)


def add_category(db, rid, cat_id="cat-1", name="Plats"):
    doc = {"_id": cat_id, "restaurant_id": rid, "name": name,
           "active": True, "display_order": 1}
    db.menu_categories.docs.append(doc)
    return doc


def owner(rid):
    return {"_id": "u-o", "role": "RESTAURANT_OWNER", "restaurant_id": rid}


def plan(db, rid, day, items, active=True):
    """Write through the step-1 router: same contract as the real dashboard."""
    body = wm.WeeklyDayUpdate(item_ids=[str(i["_id"]) for i in items])
    if not active:
        run(wm.upsert_weekly_day(day, wm.WeeklyDayUpdate(item_ids=body.item_ids),
                                 user=owner(rid)))
        return run(wm.upsert_weekly_day(day, wm.WeeklyDayUpdate(active=False),
                                        user=owner(rid)))
    return run(wm.upsert_weekly_day(day, body, user=owner(rid)))


# =============== 1-2. Active menus: monday and all seven days ===============
def test_active_menu_monday(db):
    rid = add_restaurant(db)
    add_category(db, rid)
    p = add_item(db, rid, "Poulet braisé", price=5000)
    plan(db, rid, "monday", [p])
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert out["day"] == "monday" and out["status"] == "active"
    assert len(out["items"]) == 1
    assert [i["name"] for i in out["items"]] == ["Poulet braisé"]
    assert out["items"][0]["price"] == 5000


def test_all_seven_days(db):
    rid = add_restaurant(db)
    add_category(db, rid)
    names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    for day, name, inst in zip(osvc.DAY_KEYS, names, WEEK_NOONS):
        p = add_item(db, rid, name)
        plan(db, rid, day, [p])
        out = run(osvc.get_day_menu(db, rid, now=inst))
        assert out["day"] == day
        assert out["status"] == "active"
        assert [i["name"] for i in out["items"]] == [name]
    assert len(db.weekly_menus.docs) == 7  # one doc per (restaurant, day)


# =============== 3-5. Timezone resolution ===============
def test_abidjan_timezone(db):
    rid = add_restaurant(db, tz="Africa/Abidjan")
    add_category(db, rid)
    p = add_item(db, rid, "Attiéké poisson")
    plan(db, rid, "monday", [p])
    # Abidjan is UTC+0 all year: late night and midnight UTC stay on the same
    # day, then roll over exactly at 00:00 — never dependent on machine TZ.
    assert osvc._local_day("Africa/Abidjan", MON_LATE) == "monday"
    assert osvc._local_day("Africa/Abidjan", datetime(2026, 10, 19, 23, 59, 59, tzinfo=UTC)) == "monday"
    assert osvc._local_day("Africa/Abidjan", TUE_0000) == "tuesday"
    out = run(osvc.get_day_menu(db, rid, now=MON_LATE))
    assert out["day"] == "monday" and out["status"] == "active"


def test_other_timezone_uses_local_day_not_utc_day(db):
    rid = add_restaurant(db, tz="Asia/Tokyo")
    add_category(db, rid)
    um = add_item(db, rid, "Jour UTC")
    ul = add_item(db, rid, "Jour local")
    plan(db, rid, "monday", [um])   # UTC day of TOKYO_0030
    plan(db, rid, "tuesday", [ul])  # local day in Tokyo
    out = run(osvc.get_day_menu(db, rid, now=TOKYO_0030))
    assert out["day"] == "tuesday"
    assert [i["name"] for i in out["items"]] == ["Jour local"]


def test_near_midnight_local_differs_from_utc(db):
    # Local ahead: UTC still monday, Tokyo already tuesday 00:30.
    assert TOKYO_0030.astimezone(UTC).weekday() == 0  # UTC = lundi
    assert osvc._local_day("Asia/Tokyo", TOKYO_0030) == "tuesday"
    # Local behind: UTC already tuesday, New York still monday 22:00.
    assert NY_2200.astimezone(UTC).weekday() == 1  # UTC = mardi
    assert osvc._local_day("America/New_York", NY_2200) == "monday"
    rid = add_restaurant(db, tz="America/New_York")
    add_category(db, rid)
    p = add_item(db, rid, "Late night")
    plan(db, rid, "monday", [p])
    out = run(osvc.get_day_menu(db, rid, now=NY_2200))
    assert out["day"] == "monday" and out["status"] == "active"
    assert [i["name"] for i in out["items"]] == ["Late night"]


def test_missing_timezone_falls_back_to_abidjan(db):
    rid = add_restaurant(db, tz=None)  # field absent
    add_category(db, rid)
    p = add_item(db, rid, "Sans fuseau")
    plan(db, rid, "monday", [p])
    assert osvc._local_day(None, TOKYO_0030) == osvc._local_day("Africa/Abidjan", TOKYO_0030) == "monday"
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert out["day"] == "monday" and out["status"] == "active"


def test_empty_timezone_falls_back_to_abidjan(db):
    rid = add_restaurant(db, tz="")
    assert osvc._local_day("", MON_NOON) == "monday"
    add_category(db, rid)
    p = add_item(db, rid, "Fuseau vide")
    plan(db, rid, "monday", [p])
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert out["status"] == "active" and [i["name"] for i in out["items"]] == ["Fuseau vide"]


def test_invalid_timezone_falls_back_to_abidjan_without_crash(db):
    # Documented fallback: Abidjan (monday at TOKYO_0030), NOT the machine TZ
    # and NOT a crash — a bad restaurant config must not break conversations.
    assert osvc._local_day("Not/AZone", TOKYO_0030) == "monday"
    rid = add_restaurant(db, tz="Not/AZone")
    add_category(db, rid)
    p = add_item(db, rid, "Fuseau invalide")
    plan(db, rid, "monday", [p])
    out = run(osvc.get_day_menu(db, rid, now=TOKYO_0030))
    assert out["day"] == "monday" and out["status"] == "active"


# =============== 8-9. Menu states ===============
def test_no_menu_configured(db):
    rid = add_restaurant(db)
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert out == {"day": "monday", "status": "not_configured", "items": []}


def test_inactive_menu_returns_no_items(db):
    rid = add_restaurant(db)
    add_category(db, rid)
    p = add_item(db, rid, "Poulet")
    plan(db, rid, "monday", [p], active=False)
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert out["day"] == "monday" and out["status"] == "inactive"
    assert out["items"] == []  # never silently replaced by the catalogue


# =============== 10-12. Catalogue truth for planned ids ===============
def test_deleted_product_excluded(db):
    rid = add_restaurant(db)
    add_category(db, rid)
    keep = add_item(db, rid, "Restant")
    gone = add_item(db, rid, "Supprimé")
    plan(db, rid, "monday", [keep, gone])
    db.menu_items.docs.remove(gone)
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert out["status"] == "active"
    assert [i["name"] for i in out["items"]] == ["Restant"]


def test_inactive_product_excluded(db):
    rid = add_restaurant(db)
    add_category(db, rid)
    keep = add_item(db, rid, "Actif")
    off = add_item(db, rid, "Désactivé", active=False)
    plan(db, rid, "monday", [keep, off])
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert [i["name"] for i in out["items"]] == ["Actif"]


def test_unavailable_product_kept_with_real_flag(db):
    rid = add_restaurant(db)
    add_category(db, rid)
    ok = add_item(db, rid, "Dispo")
    ko = add_item(db, rid, "Rupture", available=False, price=750)
    plan(db, rid, "monday", [ok, ko])
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert [i["name"] for i in out["items"]] == ["Dispo", "Rupture"]
    assert out["items"][1]["available"] is False   # real state, contract kept
    assert out["items"][1]["price"] == 750         # price never altered


# =============== 13-15. Isolation, order, empty menu ===============
def test_isolation_between_restaurants(db):
    ra = add_restaurant(db, public_id="pub-a")
    rb = add_restaurant(db, public_id="pub-b")
    add_category(db, ra)
    add_category(db, rb)
    ia = add_item(db, ra, "Plat A")
    ib = add_item(db, rb, "Plat B")
    plan(db, ra, "monday", [ia])
    plan(db, rb, "monday", [ib])
    out_a = run(osvc.get_day_menu(db, ra, now=MON_NOON))
    out_b = run(osvc.get_day_menu(db, rb, now=MON_NOON))
    assert [i["name"] for i in out_a["items"]] == ["Plat A"]
    assert [i["name"] for i in out_b["items"]] == ["Plat B"]
    # A third restaurant with no plan stays not_configured although two docs
    # exist for the same day.
    rc = add_restaurant(db, public_id="pub-c")
    out_c = run(osvc.get_day_menu(db, rc, now=MON_NOON))
    assert out_c["status"] == "not_configured" and out_c["items"] == []


def test_foreign_item_id_in_poisoned_doc_cannot_leak(db):
    # Data written around the router (legacy/corrupted doc): a foreign id must
    # never resolve — the catalogue lookup is tenant-scoped.
    ra = add_restaurant(db, public_id="pub-a")
    rb = add_restaurant(db, public_id="pub-b")
    add_category(db, ra)
    add_category(db, rb)
    item_a = add_item(db, ra, "Secret de A")
    item_b = add_item(db, rb, "Publique de B")
    db.weekly_menus.docs.append(
        {"restaurant_id": rb, "day": "monday", "active": True,
         "item_ids": [str(item_a["_id"]), str(item_b["_id"])],
         "created_at": "2026-10-19T00:00:00Z", "updated_at": "2026-10-19T00:00:00Z"})
    out = run(osvc.get_day_menu(db, rb, now=MON_NOON))
    assert [i["name"] for i in out["items"]] == ["Publique de B"]


def test_item_ids_order_preserved(db):
    rid = add_restaurant(db)
    add_category(db, rid)
    a = add_item(db, rid, "A")
    b = add_item(db, rid, "B")
    c = add_item(db, rid, "C")  # catalogue order: A, B, C
    plan(db, rid, "monday", [c, a, b])
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert [i["name"] for i in out["items"]] == ["C", "A", "B"]


def test_empty_menu_is_active_not_missing(db):
    rid = add_restaurant(db)
    add_category(db, rid)
    plan(db, rid, "monday", [])
    out = run(osvc.get_day_menu(db, rid, now=MON_NOON))
    assert out["day"] == "monday" and out["status"] == "active"
    assert out["items"] == []  # configured+empty stays distinct from absent


# =============== Contracts: keys, now variants ===============
def test_day_keys_match_planning_router():
    assert osvc.DAY_KEYS == wm.DAYS


def test_naive_datetime_is_read_as_utc(db):
    rid = add_restaurant(db)
    add_category(db, rid)
    p = add_item(db, rid, "Naïf")
    plan(db, rid, "monday", [p])
    out = run(osvc.get_day_menu(db, rid, now=datetime(2026, 10, 19, 12, 0)))
    assert out["day"] == "monday" and out["status"] == "active"


def test_now_none_uses_current_clock_and_finds_a_plan(db):
    # Clock-independent: all seven days are planned, so whichever local day
    # "now" resolves to, a menu exists (exercises the default path for real).
    rid = add_restaurant(db)
    add_category(db, rid)
    p = add_item(db, rid, "Toujours")
    for day in osvc.DAY_KEYS:
        plan(db, rid, day, [p])
    out = run(osvc.get_day_menu(db, rid))
    assert out["day"] in osvc.DAY_KEYS
    assert out["status"] == "active"
    assert [i["name"] for i in out["items"]] == ["Toujours"]
