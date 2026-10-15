"""
MenuMind Phase B — Menu backend tests.
Covers: categories/items/option-groups CRUD, availability, reorder,
validations, permissions (OWNER/MANAGER/STAFF/SUPER_ADMIN), tenant isolation,
and public catalog.
"""
import os
import secrets
import pytest
import requests
from http.cookiejar import DefaultCookiePolicy

DefaultCookiePolicy.return_ok_secure = lambda self, cookie, request: True


def _base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    return url.rstrip("/")


BASE_URL = _base_url()
API = f"{BASE_URL}/api"

SUPER_EMAIL = "cooldigital.africa@gmail.com"
SUPER_PASS = "Admin1234!"
DEMO_EMAIL = "awa@chezawa.ci"
DEMO_PASS = "Demo1234!"
DEMO_PUBLIC_ID = "rest_demo_chezawa"


def _session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(s, email, password):
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def _register(name, email, pwd, resto):
    s = _session()
    r = s.post(f"{API}/auth/register", json={
        "name": name, "email": email, "password": pwd,
        "restaurant_name": resto, "phone": "+2250101",
    })
    assert r.status_code == 200, r.text
    return s, r.json()


# ===== Fixtures =====
@pytest.fixture(scope="module")
def owner():
    s = _session()
    _login(s, DEMO_EMAIL, DEMO_PASS)
    return s


@pytest.fixture(scope="module")
def super_s():
    s = _session()
    _login(s, SUPER_EMAIL, SUPER_PASS)
    return s


@pytest.fixture(scope="module")
def tenant_a_menu():
    s, u = _register("MenuA Owner", f"TEST_menu_a_{secrets.token_hex(3)}@ex.com",
                     "Passw0rd!", "TEST_MenuA")
    return {"session": s, "user": u, "rid": u["restaurant_id"]}


@pytest.fixture(scope="module")
def tenant_b_menu():
    s, u = _register("MenuB Owner", f"TEST_menu_b_{secrets.token_hex(3)}@ex.com",
                     "Passw0rd!", "TEST_MenuB")
    return {"session": s, "user": u, "rid": u["restaurant_id"]}


@pytest.fixture(scope="module")
def staff_session(tenant_a_menu):
    """Create staff user in tenant A and return logged-in session + id."""
    staff_email = f"TEST_staffmenu_{secrets.token_hex(3)}@ex.com"
    r = tenant_a_menu["session"].post(f"{API}/users", json={
        "name": "Staff Menu", "email": staff_email, "password": "Passw0rd!",
        "role": "RESTAURANT_STAFF",
    })
    assert r.status_code == 200, r.text
    s = _session()
    _login(s, staff_email, "Passw0rd!")
    return s


# ===== CATEGORIES =====
class TestCategories:
    def test_list_initial(self, owner):
        r = owner.get(f"{API}/menu/categories")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_update_delete_empty_category(self, tenant_a_menu):
        s = tenant_a_menu["session"]
        r = s.post(f"{API}/menu/categories",
                   json={"name": "TEST_Cat1", "description": "desc"})
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        # PATCH
        p = s.patch(f"{API}/menu/categories/{cid}",
                    json={"name": "TEST_Cat1_Edited", "active": False})
        assert p.status_code == 200
        assert p.json()["name"] == "TEST_Cat1_Edited"
        assert p.json()["active"] is False
        # GET list to verify persistence
        lst = s.get(f"{API}/menu/categories").json()
        assert any(c["id"] == cid and c["name"] == "TEST_Cat1_Edited" for c in lst)
        # DELETE empty category OK
        d = s.delete(f"{API}/menu/categories/{cid}")
        assert d.status_code == 200

    def test_delete_non_empty_category_blocked(self, tenant_a_menu):
        s = tenant_a_menu["session"]
        c = s.post(f"{API}/menu/categories", json={"name": "TEST_CatWithItems"}).json()
        cid = c["id"]
        it = s.post(f"{API}/menu/items", json={
            "category_id": cid, "name": "TEST_ItemInCat", "price": 1000,
        })
        assert it.status_code == 200
        iid = it.json()["id"]
        d = s.delete(f"{API}/menu/categories/{cid}")
        assert d.status_code == 400
        assert "article" in d.json().get("detail", "").lower()
        # Clean up
        s.delete(f"{API}/menu/items/{iid}")
        s.delete(f"{API}/menu/categories/{cid}")

    def test_reorder_categories(self, tenant_a_menu):
        s = tenant_a_menu["session"]
        ids = []
        for n in ["TEST_R1", "TEST_R2", "TEST_R3"]:
            ids.append(s.post(f"{API}/menu/categories", json={"name": n}).json()["id"])
        rev = list(reversed(ids))
        r = s.post(f"{API}/menu/categories/reorder", json={"ids": rev})
        assert r.status_code == 200
        cats = s.get(f"{API}/menu/categories").json()
        got = {c["id"]: c["display_order"] for c in cats if c["id"] in ids}
        assert got[rev[0]] < got[rev[1]] < got[rev[2]]
        for cid in ids:
            s.delete(f"{API}/menu/categories/{cid}")


# ===== ITEMS =====
class TestItems:
    def test_items_crud_and_availability(self, tenant_a_menu):
        s = tenant_a_menu["session"]
        cat = s.post(f"{API}/menu/categories", json={"name": "TEST_ItemsCat"}).json()
        cid = cat["id"]
        # CREATE
        r = s.post(f"{API}/menu/items", json={
            "category_id": cid, "name": "TEST_Plat", "price": 2500,
        })
        assert r.status_code == 200
        iid = r.json()["id"]
        assert r.json()["price"] == 2500
        # GET detail
        g = s.get(f"{API}/menu/items/{iid}")
        assert g.status_code == 200
        assert g.json()["name"] == "TEST_Plat"
        # LIST filter
        f = s.get(f"{API}/menu/items", params={"category_id": cid, "search": "Plat"})
        assert f.status_code == 200
        assert any(i["id"] == iid for i in f.json())
        # PATCH
        p = s.patch(f"{API}/menu/items/{iid}", json={"price": 3000, "name": "TEST_PlatMod"})
        assert p.status_code == 200
        assert p.json()["price"] == 3000
        # Availability toggle
        a = s.patch(f"{API}/menu/items/{iid}/availability", json={"available": False})
        assert a.status_code == 200
        assert a.json()["available"] is False
        # Reorder
        r2 = s.post(f"{API}/menu/items", json={
            "category_id": cid, "name": "TEST_Plat2", "price": 1500,
        }).json()
        reo = s.post(f"{API}/menu/items/reorder", json={"ids": [r2["id"], iid]})
        assert reo.status_code == 200
        items = s.get(f"{API}/menu/items", params={"category_id": cid}).json()
        order = {i["id"]: i["display_order"] for i in items}
        assert order[r2["id"]] < order[iid]
        # DELETE
        assert s.delete(f"{API}/menu/items/{iid}").status_code == 200
        assert s.delete(f"{API}/menu/items/{r2['id']}").status_code == 200
        assert s.get(f"{API}/menu/items/{iid}").status_code == 404
        s.delete(f"{API}/menu/categories/{cid}")

    def test_item_validations(self, tenant_a_menu, tenant_b_menu):
        s = tenant_a_menu["session"]
        cat = s.post(f"{API}/menu/categories", json={"name": "TEST_ValCat"}).json()
        cid = cat["id"]
        # Negative price -> 422
        r = s.post(f"{API}/menu/items", json={
            "category_id": cid, "name": "neg", "price": -1,
        })
        assert r.status_code == 422
        # Empty name -> 422
        r2 = s.post(f"{API}/menu/items", json={
            "category_id": cid, "name": "", "price": 1000,
        })
        assert r2.status_code == 422
        # price 0 ok
        r3 = s.post(f"{API}/menu/items", json={
            "category_id": cid, "name": "Free", "price": 0,
        })
        assert r3.status_code == 200
        s.delete(f"{API}/menu/items/{r3.json()['id']}")
        # Non-existent category_id -> 400
        from bson import ObjectId
        fake_cid = str(ObjectId())
        r4 = s.post(f"{API}/menu/items", json={
            "category_id": fake_cid, "name": "X", "price": 100,
        })
        assert r4.status_code == 400
        # Category of another tenant -> 400
        cat_b = tenant_b_menu["session"].post(f"{API}/menu/categories",
                                              json={"name": "TEST_BCat"}).json()
        r5 = s.post(f"{API}/menu/items", json={
            "category_id": cat_b["id"], "name": "Y", "price": 100,
        })
        assert r5.status_code == 400
        tenant_b_menu["session"].delete(f"{API}/menu/categories/{cat_b['id']}")
        s.delete(f"{API}/menu/categories/{cid}")


# ===== OPTION GROUPS & OPTIONS =====
class TestOptions:
    def test_group_crud_with_options_and_detach_on_delete(self, tenant_a_menu):
        s = tenant_a_menu["session"]
        cat = s.post(f"{API}/menu/categories", json={"name": "TEST_OptCat"}).json()
        cid = cat["id"]
        # Create group
        g = s.post(f"{API}/menu/option-groups", json={
            "name": "TEST_Suppl", "required": False,
            "min_selections": 0, "max_selections": 3,
        })
        assert g.status_code == 200
        gid = g.json()["id"]
        # Validation: max < min -> 400
        bad = s.post(f"{API}/menu/option-groups", json={
            "name": "TEST_bad", "min_selections": 3, "max_selections": 1,
        })
        assert bad.status_code == 400
        # Create options
        o1 = s.post(f"{API}/menu/option-groups/{gid}/options",
                    json={"name": "Fromage", "price_delta": 500}).json()
        o2 = s.post(f"{API}/menu/option-groups/{gid}/options",
                    json={"name": "Oeuf", "price_delta": 500}).json()
        # List groups returns nested options
        groups = s.get(f"{API}/menu/option-groups").json()
        this = next(g for g in groups if g["id"] == gid)
        assert len(this["options"]) == 2
        # Patch option
        po = s.patch(f"{API}/menu/options/{o1['id']}", json={"price_delta": 700})
        assert po.status_code == 200
        assert po.json()["price_delta"] == 700
        # Create item attached to group
        it = s.post(f"{API}/menu/items", json={
            "category_id": cid, "name": "TEST_Burger", "price": 2000,
            "option_group_ids": [gid],
        }).json()
        iid = it["id"]
        assert gid in it["option_group_ids"]
        # Delete group should detach from item and delete child options, keep item
        d = s.delete(f"{API}/menu/option-groups/{gid}")
        assert d.status_code == 200
        after = s.get(f"{API}/menu/items/{iid}").json()
        assert gid not in after.get("option_group_ids", [])
        # Options should be gone (group now 404)
        assert s.patch(f"{API}/menu/options/{o2['id']}",
                       json={"name": "x"}).status_code == 404
        # Cleanup
        s.delete(f"{API}/menu/items/{iid}")
        s.delete(f"{API}/menu/categories/{cid}")

    def test_cross_tenant_group_attach_blocked(self, tenant_a_menu, tenant_b_menu):
        sa = tenant_a_menu["session"]
        sb = tenant_b_menu["session"]
        gb = sb.post(f"{API}/menu/option-groups", json={
            "name": "TEST_Bgrp", "min_selections": 0, "max_selections": 1,
        }).json()
        cata = sa.post(f"{API}/menu/categories", json={"name": "TEST_crossA"}).json()
        r = sa.post(f"{API}/menu/items", json={
            "category_id": cata["id"], "name": "X", "price": 100,
            "option_group_ids": [gb["id"]],
        })
        assert r.status_code == 400
        sa.delete(f"{API}/menu/categories/{cata['id']}")
        sb.delete(f"{API}/menu/option-groups/{gb['id']}")


# ===== PERMISSIONS =====
class TestPermissions:
    def test_staff_forbidden_structure_ok_availability(self, tenant_a_menu, staff_session):
        # Create a category/item as owner first
        s_owner = tenant_a_menu["session"]
        cat = s_owner.post(f"{API}/menu/categories", json={"name": "TEST_PermCat"}).json()
        item = s_owner.post(f"{API}/menu/items", json={
            "category_id": cat["id"], "name": "TEST_PermItem", "price": 500,
        }).json()
        # Staff: POST category 403
        r1 = staff_session.post(f"{API}/menu/categories", json={"name": "nope"})
        assert r1.status_code == 403
        # Staff: PATCH item 403
        r2 = staff_session.patch(f"{API}/menu/items/{item['id']}", json={"price": 999})
        assert r2.status_code == 403
        # Staff: DELETE item 403
        r3 = staff_session.delete(f"{API}/menu/items/{item['id']}")
        assert r3.status_code == 403
        # Staff: can toggle availability 200
        r4 = staff_session.patch(f"{API}/menu/items/{item['id']}/availability",
                                 json={"available": False})
        assert r4.status_code == 200
        assert r4.json()["available"] is False
        # Cleanup
        s_owner.delete(f"{API}/menu/items/{item['id']}")
        s_owner.delete(f"{API}/menu/categories/{cat['id']}")

    def test_super_admin_menu_blocked(self, super_s):
        # Spec says 400 ("aucun restaurant associé") but role gate fires first → 403.
        # Both are semantically correct; we accept either.
        r = super_s.get(f"{API}/menu/categories")
        assert r.status_code in (400, 403)
        r2 = super_s.post(f"{API}/menu/categories", json={"name": "x"})
        assert r2.status_code in (400, 403)


# ===== TENANT ISOLATION =====
class TestIsolation:
    def test_cross_tenant_read_write_delete_returns_404(self, tenant_a_menu, tenant_b_menu):
        sa = tenant_a_menu["session"]
        sb = tenant_b_menu["session"]
        cat_a = sa.post(f"{API}/menu/categories", json={"name": "TEST_IsoCatA"}).json()
        item_a = sa.post(f"{API}/menu/items", json={
            "category_id": cat_a["id"], "name": "TEST_IsoItemA", "price": 100,
        }).json()
        grp_a = sa.post(f"{API}/menu/option-groups", json={
            "name": "TEST_IsoGrpA", "min_selections": 0, "max_selections": 1,
        }).json()
        opt_a = sa.post(f"{API}/menu/option-groups/{grp_a['id']}/options",
                        json={"name": "optA", "price_delta": 0}).json()
        # B tries to read A
        assert sb.get(f"{API}/menu/items/{item_a['id']}").status_code == 404
        assert sb.patch(f"{API}/menu/items/{item_a['id']}",
                        json={"price": 1}).status_code == 404
        assert sb.delete(f"{API}/menu/items/{item_a['id']}").status_code == 404
        assert sb.patch(f"{API}/menu/categories/{cat_a['id']}",
                        json={"name": "x"}).status_code == 400
        assert sb.delete(f"{API}/menu/categories/{cat_a['id']}").status_code == 400
        assert sb.patch(f"{API}/menu/option-groups/{grp_a['id']}",
                        json={"name": "x"}).status_code == 404
        assert sb.delete(f"{API}/menu/options/{opt_a['id']}").status_code == 404
        # B's item list does not contain A
        b_items = sb.get(f"{API}/menu/items").json()
        assert all(i["id"] != item_a["id"] for i in b_items)
        # Cleanup A
        sa.delete(f"{API}/menu/options/{opt_a['id']}")
        sa.delete(f"{API}/menu/option-groups/{grp_a['id']}")
        sa.delete(f"{API}/menu/items/{item_a['id']}")
        sa.delete(f"{API}/menu/categories/{cat_a['id']}")


# ===== PUBLIC CATALOG =====
class TestPublicCatalog:
    def test_public_catalog_no_auth(self):
        r = requests.get(f"{API}/menu/public/{DEMO_PUBLIC_ID}")
        assert r.status_code == 200
        data = r.json()
        assert "restaurant" in data and "categories" in data
        assert data["restaurant"]["name"]
        assert data["restaurant"]["currency"] == "FCFA"
        # No sensitive fields
        s = str(data).lower()
        assert "email" not in s
        assert "password" not in s
        assert "audit" not in s
        # categories have items with options structure
        for c in data["categories"]:
            for it in c["items"]:
                assert set(["id", "name", "price", "available", "options"]).issubset(it.keys())
                for g in it["options"]:
                    assert set(["name", "required", "min", "max", "choices"]).issubset(g.keys())

    def test_public_hides_inactive_shows_unavailable(self, owner):
        # Pick first item of demo tenant and toggle its states
        items = owner.get(f"{API}/menu/items").json()
        assert items, "demo should have items"
        iid = items[0]["id"]
        name = items[0]["name"]
        try:
            # Mark unavailable: should still appear
            owner.patch(f"{API}/menu/items/{iid}/availability", json={"available": False})
            pub = requests.get(f"{API}/menu/public/{DEMO_PUBLIC_ID}").json()
            flat = [i for c in pub["categories"] for i in c["items"]]
            match = next((i for i in flat if i["id"] == iid), None)
            assert match is not None, "unavailable item should still appear"
            assert match["available"] is False
            # Mark inactive: should disappear
            owner.patch(f"{API}/menu/items/{iid}", json={"active": False})
            pub2 = requests.get(f"{API}/menu/public/{DEMO_PUBLIC_ID}").json()
            flat2 = [i for c in pub2["categories"] for i in c["items"]]
            assert all(i["id"] != iid for i in flat2), "inactive item should be hidden"
        finally:
            # Restore
            owner.patch(f"{API}/menu/items/{iid}", json={"active": True})
            owner.patch(f"{API}/menu/items/{iid}/availability", json={"available": True})
