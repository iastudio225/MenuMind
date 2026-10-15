"""Tests D1.46 — Supervision SaaS : restaurants (détail/édition/suppression douce) + catalogue plans."""
import os
import secrets
from http.cookiejar import DefaultCookiePolicy

import pytest
import requests
from pymongo import MongoClient

DefaultCookiePolicy.return_ok_secure = lambda self, cookie, request: True

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8002").rstrip("/")
API = f"{BASE_URL}/api"

_mongo = MongoClient("mongodb://127.0.0.1:27017/")
_db = _mongo["restoia-test"]

SUPER_EMAIL = os.environ.get("ADMIN_EMAIL", "cooldigital.africa@gmail.com")
SUPER_PASS = os.environ.get("ADMIN_PASSWORD", "Admin1234!")
DEMO_EMAIL = "awa@chezawa.ci"
DEMO_PASS = "Demo1234!"


def new_session():
    return requests.Session()


def login(session, email, password):
    return session.post(f"{API}/auth/login", json={"email": email, "password": password})


@pytest.fixture(scope="module")
def admin():
    s = new_session()
    r = login(s, SUPER_EMAIL, SUPER_PASS)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def owner():
    s = new_session()
    r = login(s, DEMO_EMAIL, DEMO_PASS)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture()
def temp_restaurant(admin):
    suffix = secrets.token_hex(3)
    r = admin.post(f"{API}/admin/restaurants", json={
        "name": f"TEST_Admin_{suffix}", "owner_name": "Test Owner",
        "owner_email": f"test_admin_{suffix}@example.com",
        "owner_password": "Test1234!", "plan": "STARTER",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    yield data
    admin.delete(f"{API}/admin/restaurants/{data['id']}")
    _db.restaurants.delete_one({"public_id": data["public_id"]})
    _db.users.delete_many({"email": f"test_admin_{suffix}@example.com"})


@pytest.fixture()
def temp_plan(admin):
    code = "TST" + secrets.token_hex(3).upper()
    r = admin.post(f"{API}/admin/plans", json={
        "code": code, "name": "Plan Test", "price": 10000, "currency": "FCFA",
        "limits": {"max_orders_per_month": 10, "max_ai_conversations": 10,
                   "max_users": 1, "whatsapp_enabled": False,
                   "analytics_enabled": False, "custom_branding": False},
    })
    assert r.status_code == 200, r.text
    data = r.json()
    yield data
    admin.delete(f"{API}/admin/plans/{code}")


# ---- Accès ----
def test_owner_cannot_access_admin(owner):
    for method, path in [("get", "/admin/metrics"), ("get", "/admin/restaurants"),
                         ("get", "/admin/plans")]:
        r = getattr(owner, method)(f"{API}{path}")
        assert r.status_code == 403, path


def test_metrics_excludes_deleted(admin):
    r = admin.get(f"{API}/admin/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["total_restaurants"] == data["active_restaurants"] + data["suspended_restaurants"]


# ---- Détail / édition ----
def test_restaurant_detail(admin, temp_restaurant):
    r = admin.get(f"{API}/admin/restaurants/{temp_restaurant['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == temp_restaurant["name"]
    assert isinstance(data.get("users"), list)
    assert any(u["email"].startswith("test_admin_") for u in data["users"])


def test_update_restaurant_and_license(admin, temp_restaurant):
    rid = temp_restaurant["id"]
    r = admin.patch(f"{API}/admin/restaurants/{rid}", json={
        "city": "Yamoussoukro", "plan_expires_at": "2030-12-31",
    })
    assert r.status_code == 200, r.text
    r2 = admin.get(f"{API}/admin/restaurants/{rid}")
    data = r2.json()
    assert data["city"] == "Yamoussoukro"
    assert data["plan_expires_at"].startswith("2030-12-31")


def test_update_with_unknown_plan_rejected(admin, temp_restaurant):
    r = admin.patch(f"{API}/admin/restaurants/{temp_restaurant['id']}", json={"plan": "NOPE"})
    assert r.status_code == 400


# ---- Suppression douce ----
def test_soft_delete_hides_everywhere(admin, temp_restaurant):
    rid = temp_restaurant["id"]
    r = admin.delete(f"{API}/admin/restaurants/{rid}")
    assert r.status_code == 200
    listed = admin.get(f"{API}/admin/restaurants").json()
    assert rid not in {x["id"] for x in listed}
    r2 = admin.delete(f"{API}/admin/restaurants/{rid}")
    assert r2.status_code == 404
    pub = requests.get(f"{BASE_URL}/widget.js")
    assert pub.status_code == 200


def test_soft_deleted_restaurant_public_menu_404(admin):
    suffix = secrets.token_hex(3)
    r = admin.post(f"{API}/admin/restaurants", json={
        "name": f"TEST_Pub_{suffix}", "owner_name": "T",
        "owner_email": f"test_pub_{suffix}@example.com",
        "owner_password": "Test1234!", "plan": "STARTER",
    })
    rid = r.json()["id"]
    public_id = r.json()["public_id"]
    ok_menu = requests.get(f"{API}/public/menu/{public_id}")
    assert ok_menu.status_code == 200
    admin.delete(f"{API}/admin/restaurants/{rid}")
    gone = requests.get(f"{API}/public/menu/{public_id}")
    assert gone.status_code == 404
    _db.restaurants.delete_one({"public_id": public_id})
    _db.users.delete_many({"email": f"test_pub_{suffix}@example.com"})


# ---- Plans ----
def test_plans_include_assignment_count(admin, temp_restaurant):
    r = admin.get(f"{API}/admin/plans")
    assert r.status_code == 200
    starter = next(p for p in r.json() if p["code"] == "STARTER")
    assert starter["restaurants_count"] >= 1


def test_plan_crud_roundtrip(admin, temp_plan):
    r = admin.patch(f"{API}/admin/plans/{temp_plan['code']}", json={"price": 12345})
    assert r.status_code == 200
    r2 = admin.get(f"{API}/admin/plans")
    updated = next(p for p in r2.json() if p["code"] == temp_plan["code"])
    assert updated["price"] == 12345


def test_duplicate_plan_code_rejected(admin, temp_plan):
    r = admin.post(f"{API}/admin/plans", json={
        "code": temp_plan["code"], "name": "Dup", "price": 1, "currency": "FCFA", "limits": {},
    })
    assert r.status_code == 400


def test_delete_assigned_plan_conflict(admin, temp_restaurant, temp_plan):
    r = admin.patch(f"{API}/admin/restaurants/{temp_restaurant['id']}",
                    json={"plan": temp_plan["code"]})
    assert r.status_code == 200
    d = admin.delete(f"{API}/admin/plans/{temp_plan['code']}")
    assert d.status_code == 409
    # désassigner puis supprimer
    r2 = admin.patch(f"{API}/admin/restaurants/{temp_restaurant['id']}", json={"plan": "STARTER"})
    assert r2.status_code == 200
    d2 = admin.delete(f"{API}/admin/plans/{temp_plan['code']}")
    assert d2.status_code == 200
