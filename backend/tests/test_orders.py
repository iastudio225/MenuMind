"""
RestoIA Phase C — Order engine backend tests.
Covers: public cart (CRUD + server-side pricing), validate (price change / availability /
required groups), delivery zones (public), order creation with snapshots + idempotency,
revalidation at order-time (409), tracking (public, sanitized), dashboard orders
(list/filter/detail/status transitions/cancel), permissions, tenant isolation.
"""
import os
import secrets
import uuid
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


def _s():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(s, email, pw):
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()


def _register(name, email, pw, resto):
    s = _s()
    r = s.post(f"{API}/auth/register", json={
        "name": name, "email": email, "password": pw,
        "restaurant_name": resto, "phone": "+2250101",
    })
    assert r.status_code == 200, r.text
    return s, r.json()


# =============== FIXTURES ===============
@pytest.fixture(scope="module")
def owner():
    s = _s()
    _login(s, DEMO_EMAIL, DEMO_PASS)
    return s


@pytest.fixture(scope="module")
def menu():
    """Fetch demo public menu to resolve ids for Poulet braisé + Fromage + Accompagnement."""
    r = requests.get(f"{API}/menu/public/{DEMO_PUBLIC_ID}")
    assert r.status_code == 200
    data = r.json()
    poulet = None
    for c in data["categories"]:
        for it in c["items"]:
            if it["name"] == "Poulet braisé":
                poulet = it
                break
    assert poulet, "seed should contain 'Poulet braisé'"
    accompagnement = next((g for g in poulet["options"] if g["name"] == "Accompagnement"), None)
    supplements = next((g for g in poulet["options"] if "upplément" in g["name"]), None)
    assert accompagnement and accompagnement["required"]
    assert supplements
    fromage = next((c for c in supplements["choices"] if c["name"] == "Fromage"), None)
    assert fromage
    alloco = next((c for c in accompagnement["choices"] if "lloco" in c["name"].lower() or "lloco" in c["name"]), None)
    assert alloco, f"Alloco not found in {accompagnement['choices']}"
    return {"poulet_id": poulet["id"], "poulet_price": poulet["price"],
            "fromage_id": fromage["id"], "fromage_delta": fromage["price_delta"],
            "accompagnement_group_id": accompagnement["id"], "alloco_id": alloco["id"]}


@pytest.fixture(scope="module")
def zones_demo():
    r = requests.get(f"{API}/public/delivery-zones/{DEMO_PUBLIC_ID}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 3
    return {z["name"]: z for z in data}


@pytest.fixture
def new_cart():
    r = requests.post(f"{API}/public/cart", json={"restaurant_public_id": DEMO_PUBLIC_ID})
    assert r.status_code == 200
    return r.json()["cart_id"]


# =============== 1. CART CRUD + PRICING ===============
class TestCartPricingPublic:
    def test_create_cart_and_get(self):
        r = requests.post(f"{API}/public/cart", json={"restaurant_public_id": DEMO_PUBLIC_ID})
        assert r.status_code == 200
        cid = r.json()["cart_id"]
        g = requests.get(f"{API}/public/cart/{cid}")
        assert g.status_code == 200
        data = g.json()
        assert data["cart_id"] == cid
        assert data["subtotal"] == 0
        assert data["items"] == []

    def test_price_calculation_poulet_x2(self, menu, new_cart):
        """2 x Poulet braisé (5000) with required Alloco (0 delta) = 10000."""
        r = requests.post(f"{API}/public/cart/{new_cart}/items", json={
            "item_id": menu["poulet_id"], "quantity": 2,
            "option_ids": [menu["alloco_id"]],
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["subtotal"] == 10000
        assert len(data["items"]) == 1
        line = data["items"][0]
        assert line["quantity"] == 2
        assert line["unit_price"] == 5000
        assert line["line_total"] == 10000

    def test_price_with_fromage_option(self, menu, new_cart):
        """1 x Poulet (5000) + Alloco(0) + Fromage(+500) = 5500."""
        r = requests.post(f"{API}/public/cart/{new_cart}/items", json={
            "item_id": menu["poulet_id"], "quantity": 1,
            "option_ids": [menu["alloco_id"], menu["fromage_id"]],
        })
        assert r.status_code == 200, r.text
        assert r.json()["subtotal"] == 5500

    def test_update_quantity_and_total(self, menu, new_cart):
        """Add 1x poulet+fromage, update to 2 -> 11000."""
        add = requests.post(f"{API}/public/cart/{new_cart}/items", json={
            "item_id": menu["poulet_id"], "quantity": 1,
            "option_ids": [menu["alloco_id"], menu["fromage_id"]],
        })
        assert add.status_code == 200
        line_id = add.json()["items"][0]["cart_item_id"]
        upd = requests.patch(f"{API}/public/cart/{new_cart}/items/{line_id}",
                             json={"quantity": 2})
        assert upd.status_code == 200
        assert upd.json()["subtotal"] == 11000

    def test_remove_item(self, menu, new_cart):
        add = requests.post(f"{API}/public/cart/{new_cart}/items", json={
            "item_id": menu["poulet_id"], "quantity": 1,
            "option_ids": [menu["alloco_id"]],
        })
        line_id = add.json()["items"][0]["cart_item_id"]
        d = requests.delete(f"{API}/public/cart/{new_cart}/items/{line_id}")
        assert d.status_code == 200
        assert d.json()["subtotal"] == 0

    def test_clear_cart(self, menu, new_cart):
        requests.post(f"{API}/public/cart/{new_cart}/items", json={
            "item_id": menu["poulet_id"], "quantity": 1,
            "option_ids": [menu["alloco_id"]],
        })
        d = requests.delete(f"{API}/public/cart/{new_cart}")
        assert d.status_code == 200
        g = requests.get(f"{API}/public/cart/{new_cart}").json()
        assert g["items"] == []


# =============== 2. DELIVERY ZONES PUBLIC ===============
class TestPublicZones:
    def test_zones_only_active_with_fees(self, zones_demo):
        assert "Cocody" in zones_demo and zones_demo["Cocody"]["fee"] == 1000
        assert "Marcory" in zones_demo and zones_demo["Marcory"]["fee"] == 1500
        assert "Yopougon" in zones_demo and zones_demo["Yopougon"]["fee"] == 2000
        for z in zones_demo.values():
            assert z.get("active", True)


# =============== 3. VALIDATE ===============
class TestValidate:
    def test_validate_empty_cart(self, new_cart):
        r = requests.post(f"{API}/public/cart/{new_cart}/validate")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is False
        assert any("vide" in i.lower() for i in data["issues"])

    def test_validate_ok(self, menu, new_cart):
        requests.post(f"{API}/public/cart/{new_cart}/items", json={
            "item_id": menu["poulet_id"], "quantity": 1,
            "option_ids": [menu["alloco_id"]],
        })
        r = requests.post(f"{API}/public/cart/{new_cart}/validate")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True, data["issues"]

    def test_validate_detects_unavailable(self, owner, menu, new_cart):
        """Add item then flip availability=False -> validate false."""
        requests.post(f"{API}/public/cart/{new_cart}/items", json={
            "item_id": menu["poulet_id"], "quantity": 1,
            "option_ids": [menu["alloco_id"]],
        })
        owner.patch(f"{API}/menu/items/{menu['poulet_id']}/availability", json={"available": False})
        try:
            r = requests.post(f"{API}/public/cart/{new_cart}/validate")
            assert r.status_code == 200
            data = r.json()
            assert data["valid"] is False
            assert any("disponible" in i.lower() for i in data["issues"])
        finally:
            owner.patch(f"{API}/menu/items/{menu['poulet_id']}/availability", json={"available": True})

    def test_validate_detects_price_change(self, owner, menu, new_cart):
        """Add item at current price then bump item price -> validate flags price changed."""
        orig = menu["poulet_price"]
        requests.post(f"{API}/public/cart/{new_cart}/items", json={
            "item_id": menu["poulet_id"], "quantity": 1,
            "option_ids": [menu["alloco_id"]],
        })
        owner.patch(f"{API}/menu/items/{menu['poulet_id']}", json={"price": orig + 1000})
        try:
            r = requests.post(f"{API}/public/cart/{new_cart}/validate")
            assert r.status_code == 200
            data = r.json()
            assert data["valid"] is False
            assert any("prix" in i.lower() and "chang" in i.lower() for i in data["issues"])
        finally:
            owner.patch(f"{API}/menu/items/{menu['poulet_id']}", json={"price": orig})

    def test_add_without_required_group_then_validate_fails(self, menu, new_cart):
        """Add poulet WITHOUT the required Accompagnement -> validate flags."""
        r = requests.post(f"{API}/public/cart/{new_cart}/items", json={
            "item_id": menu["poulet_id"], "quantity": 1, "option_ids": [],
        })
        assert r.status_code == 200
        v = requests.post(f"{API}/public/cart/{new_cart}/validate").json()
        assert v["valid"] is False
        assert any("Accompagnement" in i for i in v["issues"])


# =============== 4. ORDER CREATION ===============
def _make_full_cart(menu):
    r = requests.post(f"{API}/public/cart", json={"restaurant_public_id": DEMO_PUBLIC_ID})
    cid = r.json()["cart_id"]
    requests.post(f"{API}/public/cart/{cid}/items", json={
        "item_id": menu["poulet_id"], "quantity": 2,
        "option_ids": [menu["alloco_id"], menu["fromage_id"]],
    })
    return cid


class TestOrderCreation:
    def test_delivery_order_total_12000(self, menu, zones_demo):
        """2 x Poulet (5000+500=5500) = 11000 + Cocody(1000) = 12000."""
        cid = _make_full_cart(menu)
        key = str(uuid.uuid4())
        r = requests.post(
            f"{API}/public/orders",
            headers={"Idempotency-Key": key},
            json={"cart_id": cid, "order_type": "DELIVERY",
                  "delivery_zone_id": zones_demo["Cocody"]["id"],
                  "customer": {"first_name": "TEST_Jean", "phone": "+2250707070707",
                               "address": "Rue 12, Cocody"},
                  "customer_note": "Interphone 3"})
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["subtotal"] == 11000
        assert o["delivery_fee"] == 1000
        assert o["total"] == 12000
        assert o["reference"].startswith("CMD-")
        assert o.get("tracking_token")
        assert o["status"] == "PENDING"

    def test_delivery_without_address_400(self, menu, zones_demo):
        cid = _make_full_cart(menu)
        r = requests.post(
            f"{API}/public/orders",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"cart_id": cid, "order_type": "DELIVERY",
                  "delivery_zone_id": zones_demo["Cocody"]["id"],
                  "customer": {"first_name": "T", "phone": "+2250707070708", "address": ""}})
        assert r.status_code == 400

    def test_delivery_without_zone_400(self, menu):
        cid = _make_full_cart(menu)
        r = requests.post(
            f"{API}/public/orders",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"cart_id": cid, "order_type": "DELIVERY",
                  "customer": {"first_name": "T", "phone": "+2250707070709",
                               "address": "quelque part"}})
        assert r.status_code == 400

    def test_pickup_no_fee_no_address(self, menu):
        cid = _make_full_cart(menu)
        r = requests.post(
            f"{API}/public/orders",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"cart_id": cid, "order_type": "PICKUP",
                  "customer": {"first_name": "T", "phone": "+2250707070710"}})
        assert r.status_code == 200, r.text
        assert r.json()["delivery_fee"] == 0
        assert r.json()["total"] == 11000

    def test_idempotency_same_key_single_order(self, menu, zones_demo):
        cid = _make_full_cart(menu)
        key = str(uuid.uuid4())
        headers = {"Idempotency-Key": key}
        payload = {"cart_id": cid, "order_type": "DELIVERY",
                   "delivery_zone_id": zones_demo["Marcory"]["id"],
                   "customer": {"first_name": "Idem", "phone": "+2250707070711",
                                "address": "Marcory 5"}}
        r1 = requests.post(f"{API}/public/orders", headers=headers, json=payload)
        r2 = requests.post(f"{API}/public/orders", headers=headers, json=payload)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["reference"] == r2.json()["reference"]

    def test_revalidation_at_order_time_409(self, owner, menu, zones_demo):
        """Build cart, then flip item unavailable, then POST order -> 409."""
        cid = _make_full_cart(menu)
        owner.patch(f"{API}/menu/items/{menu['poulet_id']}/availability", json={"available": False})
        try:
            r = requests.post(
                f"{API}/public/orders",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={"cart_id": cid, "order_type": "DELIVERY",
                      "delivery_zone_id": zones_demo["Cocody"]["id"],
                      "customer": {"first_name": "T", "phone": "+2250707070712",
                                   "address": "ici"}})
            assert r.status_code == 409, r.text
        finally:
            owner.patch(f"{API}/menu/items/{menu['poulet_id']}/availability", json={"available": True})


# =============== 5. SNAPSHOT (price change after order) ===============
class TestSnapshot:
    def test_price_change_after_order_does_not_affect_total(self, owner, menu, zones_demo):
        cid = _make_full_cart(menu)
        r = requests.post(
            f"{API}/public/orders",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"cart_id": cid, "order_type": "DELIVERY",
                  "delivery_zone_id": zones_demo["Cocody"]["id"],
                  "customer": {"first_name": "Snap", "phone": "+2250707070713",
                               "address": "snap street"}})
        assert r.status_code == 200
        total_before = r.json()["total"]
        tracking = r.json()["tracking_token"]
        orig_price = menu["poulet_price"]
        owner.patch(f"{API}/menu/items/{menu['poulet_id']}", json={"price": orig_price + 2000})
        try:
            tr = requests.get(f"{API}/public/orders/{tracking}")
            assert tr.status_code == 200
            assert tr.json()["total"] == total_before
        finally:
            owner.patch(f"{API}/menu/items/{menu['poulet_id']}", json={"price": orig_price})


# =============== 6. TRACKING (public, sanitized) ===============
class TestTracking:
    def test_tracking_returns_sanitized_view(self, menu, zones_demo):
        cid = _make_full_cart(menu)
        r = requests.post(
            f"{API}/public/orders",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"cart_id": cid, "order_type": "DELIVERY",
                  "delivery_zone_id": zones_demo["Cocody"]["id"],
                  "customer": {"first_name": "Track", "phone": "+2250707070714",
                               "email": "secret@example.com", "address": "ici"}})
        tok = r.json()["tracking_token"]
        tr = requests.get(f"{API}/public/orders/{tok}").json()
        # No raw customer_id/restaurant_id/audit; email of customer must not leak
        s = str(tr).lower()
        assert "secret@example.com" not in s
        assert "restaurant_id" not in tr
        assert "idempotency_key" not in tr
        assert tr["reference"].startswith("CMD-")

    def test_tracking_404(self):
        r = requests.get(f"{API}/public/orders/nonexistent_token_xyz")
        assert r.status_code == 404


# =============== 7. DASHBOARD ORDERS + TRANSITIONS ===============
class TestDashboardOrders:
    def _place(self, menu, zones_demo, otype="DELIVERY"):
        cid = _make_full_cart(menu)
        payload = {"cart_id": cid, "order_type": otype,
                   "customer": {"first_name": "DashCust", "phone": f"+22507{secrets.token_hex(5)}",
                                "address": "x"}}
        if otype == "DELIVERY":
            payload["delivery_zone_id"] = zones_demo["Cocody"]["id"]
        r = requests.post(f"{API}/public/orders", headers={"Idempotency-Key": str(uuid.uuid4())}, json=payload)
        assert r.status_code == 200, r.text
        return r.json()

    def test_list_filter_status_period(self, owner):
        r = owner.get(f"{API}/orders")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        r2 = owner.get(f"{API}/orders", params={"status": "PENDING"})
        assert r2.status_code == 200
        assert all(o["status"] == "PENDING" for o in r2.json())
        r3 = owner.get(f"{API}/orders", params={"period": "today"})
        assert r3.status_code == 200

    def test_valid_transition_flow_delivery(self, owner, menu, zones_demo):
        o = self._place(menu, zones_demo, "DELIVERY")
        # find its id in dashboard
        lst = owner.get(f"{API}/orders").json()
        oid = next(x["id"] for x in lst if x["reference"] == o["reference"])
        for st in ["CONFIRMED", "PREPARING", "READY", "OUT_FOR_DELIVERY", "DELIVERED"]:
            r = owner.patch(f"{API}/orders/{oid}/status", json={"status": st})
            assert r.status_code == 200, f"{st}: {r.text}"
            assert r.json()["status"] == st
        # DELIVERED -> * forbidden
        r = owner.patch(f"{API}/orders/{oid}/status", json={"status": "PREPARING"})
        assert r.status_code == 400

    def test_illegal_skip_transition(self, owner, menu, zones_demo):
        o = self._place(menu, zones_demo, "DELIVERY")
        lst = owner.get(f"{API}/orders").json()
        oid = next(x["id"] for x in lst if x["reference"] == o["reference"])
        # CONFIRMED -> DELIVERED illegal
        owner.patch(f"{API}/orders/{oid}/status", json={"status": "CONFIRMED"})
        r = owner.patch(f"{API}/orders/{oid}/status", json={"status": "DELIVERED"})
        assert r.status_code == 400

    def test_out_for_delivery_only_delivery_type(self, owner, menu, zones_demo):
        """PICKUP flow: READY -> DELIVERED ok; OUT_FOR_DELIVERY forbidden."""
        o = self._place(menu, zones_demo, "PICKUP")
        lst = owner.get(f"{API}/orders").json()
        oid = next(x["id"] for x in lst if x["reference"] == o["reference"])
        for st in ["CONFIRMED", "PREPARING", "READY"]:
            r = owner.patch(f"{API}/orders/{oid}/status", json={"status": st})
            assert r.status_code == 200, r.text
        r = owner.patch(f"{API}/orders/{oid}/status", json={"status": "OUT_FOR_DELIVERY"})
        assert r.status_code == 400
        r2 = owner.patch(f"{API}/orders/{oid}/status", json={"status": "DELIVERED"})
        assert r2.status_code == 200

    def test_get_order_with_history(self, owner, menu, zones_demo):
        o = self._place(menu, zones_demo, "DELIVERY")
        lst = owner.get(f"{API}/orders").json()
        oid = next(x["id"] for x in lst if x["reference"] == o["reference"])
        owner.patch(f"{API}/orders/{oid}/status", json={"status": "CONFIRMED"})
        d = owner.get(f"{API}/orders/{oid}")
        assert d.status_code == 200
        data = d.json()
        assert "history" in data and len(data["history"]) >= 2

    def test_cancel_pending_ok_then_delivered_blocked(self, owner, menu, zones_demo):
        o = self._place(menu, zones_demo, "DELIVERY")
        lst = owner.get(f"{API}/orders").json()
        oid = next(x["id"] for x in lst if x["reference"] == o["reference"])
        c = owner.post(f"{API}/orders/{oid}/cancel", json={"reason": "test"})
        assert c.status_code == 200
        assert c.json()["status"] == "CANCELLED"
        # Cancel again blocked
        c2 = owner.post(f"{API}/orders/{oid}/cancel", json={"reason": "again"})
        assert c2.status_code == 400

    def test_cancel_delivered_blocked(self, owner, menu, zones_demo):
        o = self._place(menu, zones_demo, "DELIVERY")
        lst = owner.get(f"{API}/orders").json()
        oid = next(x["id"] for x in lst if x["reference"] == o["reference"])
        for st in ["CONFIRMED", "PREPARING", "READY", "OUT_FOR_DELIVERY", "DELIVERED"]:
            owner.patch(f"{API}/orders/{oid}/status", json={"status": st})
        c = owner.post(f"{API}/orders/{oid}/cancel", json={"reason": "no"})
        assert c.status_code == 400


# =============== 8. CUSTOMERS ===============
class TestCustomers:
    def test_customer_upsert_and_list(self, owner, menu, zones_demo):
        # Place order with unique phone to create customer
        phone = f"+22505{secrets.token_hex(5)}"
        cid = _make_full_cart(menu)
        requests.post(
            f"{API}/public/orders",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"cart_id": cid, "order_type": "PICKUP",
                  "customer": {"first_name": "TEST_UpsertCust", "phone": phone}})
        lst = owner.get(f"{API}/customers")
        assert lst.status_code == 200
        rows = lst.json()
        match = next((c for c in rows if c["phone"] == phone.replace("+", "+") or c["phone"].endswith(phone[-5:])), None)
        assert match, f"customer with phone {phone} not found"
        assert match["orders_count"] >= 1
        assert match["total_spent"] >= 11000

        # Second order same phone -> same customer
        cid2 = _make_full_cart(menu)
        requests.post(
            f"{API}/public/orders",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"cart_id": cid2, "order_type": "PICKUP",
                  "customer": {"first_name": "TEST_UpsertCust", "phone": phone}})
        lst2 = owner.get(f"{API}/customers").json()
        match2 = next(c for c in lst2 if c["id"] == match["id"])
        assert match2["orders_count"] >= 2


# =============== 9. PERMISSIONS ===============
@pytest.fixture(scope="module")
def tenant_a_c():
    s, u = _register("CA Owner", f"TEST_ownc_a_{secrets.token_hex(3)}@ex.com",
                     "Passw0rd!", f"TEST_C_A_{secrets.token_hex(3)}")
    return {"session": s, "user": u, "rid": u["restaurant_id"]}


@pytest.fixture(scope="module")
def tenant_b_c():
    s, u = _register("CB Owner", f"TEST_ownc_b_{secrets.token_hex(3)}@ex.com",
                     "Passw0rd!", f"TEST_C_B_{secrets.token_hex(3)}")
    return {"session": s, "user": u, "rid": u["restaurant_id"]}


@pytest.fixture(scope="module")
def staff_a(tenant_a_c):
    email = f"TEST_staffc_{secrets.token_hex(3)}@ex.com"
    r = tenant_a_c["session"].post(f"{API}/users", json={
        "name": "Staff C", "email": email, "password": "Passw0rd!",
        "role": "RESTAURANT_STAFF"})
    assert r.status_code == 200, r.text
    s = _s()
    _login(s, email, "Passw0rd!")
    return s


class TestPermissions:
    def test_staff_can_list_orders(self, staff_a):
        r = staff_a.get(f"{API}/orders")
        assert r.status_code == 200

    def test_staff_cannot_list_customers(self, staff_a):
        r = staff_a.get(f"{API}/customers")
        assert r.status_code == 403

    def test_staff_cannot_create_zone(self, staff_a):
        r = staff_a.post(f"{API}/delivery/zones", json={"name": "ZX", "fee": 1000})
        assert r.status_code == 403

    def test_staff_cannot_cancel_order(self, owner, menu, zones_demo, staff_a):
        """Staff on demo tenant: use its own tenant actually; need an order in staff tenant."""
        # Create minimal item/zone in staff's tenant to place an order? Simpler: test demo tenant.
        # Instead: ensure staff hitting /cancel in demo returns 403 because of role gate.
        r = staff_a.post(f"{API}/orders/000000000000000000000000/cancel", json={"reason": "x"})
        assert r.status_code == 403

    def test_staff_can_patch_status(self, owner, menu, zones_demo):
        """Demo owner creates order, demo-staff would need to exist for a fair test.
        Instead we just verify the role gate on the endpoint allows STAFF (not 403 from role).
        We use a fake id — expect 404 (passed role gate) or 400, not 403.
        """
        # Create a staff user in demo tenant for this check
        demo_s = _s()
        _login(demo_s, DEMO_EMAIL, DEMO_PASS)
        staff_email = f"TEST_demo_staff_{secrets.token_hex(3)}@ex.com"
        r = demo_s.post(f"{API}/users", json={
            "name": "Demo Staff", "email": staff_email, "password": "Passw0rd!",
            "role": "RESTAURANT_STAFF"})
        if r.status_code != 200:
            pytest.skip("could not create demo staff")
        ss = _s()
        _login(ss, staff_email, "Passw0rd!")
        # place an order
        cid = _make_full_cart(menu)
        placed = requests.post(f"{API}/public/orders",
                               headers={"Idempotency-Key": str(uuid.uuid4())},
                               json={"cart_id": cid, "order_type": "PICKUP",
                                     "customer": {"first_name": "Perm", "phone": f"+22505{secrets.token_hex(5)}"}})
        assert placed.status_code == 200
        ref = placed.json()["reference"]
        lst = demo_s.get(f"{API}/orders").json()
        oid = next(x["id"] for x in lst if x["reference"] == ref)
        r2 = ss.patch(f"{API}/orders/{oid}/status", json={"status": "CONFIRMED"})
        assert r2.status_code == 200, r2.text
        # And staff cannot cancel
        r3 = ss.post(f"{API}/orders/{oid}/cancel", json={"reason": "x"})
        assert r3.status_code == 403


# =============== 10. TENANT ISOLATION ===============
class TestIsolationC:
    def test_b_cannot_see_a_orders_or_customers(self, tenant_a_c, tenant_b_c):
        # A has no items/zones in fresh tenant, so skip creating orders in A.
        # Just verify empty tenants show empty lists and cross-tenant GET 404.
        lst_a = tenant_a_c["session"].get(f"{API}/orders").json()
        lst_b = tenant_b_c["session"].get(f"{API}/orders").json()
        assert lst_a == []
        assert lst_b == []
        # fake order id in B
        r = tenant_b_c["session"].get(f"{API}/orders/000000000000000000000000")
        assert r.status_code == 404

        cust_a = tenant_a_c["session"].get(f"{API}/customers").json()
        cust_b = tenant_b_c["session"].get(f"{API}/customers").json()
        assert cust_a == []
        assert cust_b == []

    def test_b_cannot_delete_a_zone(self, tenant_a_c, tenant_b_c):
        za = tenant_a_c["session"].post(f"{API}/delivery/zones",
                                        json={"name": "TEST_ZoneA", "fee": 500}).json()
        r = tenant_b_c["session"].delete(f"{API}/delivery/zones/{za['id']}")
        assert r.status_code == 404
        # cleanup
        tenant_a_c["session"].delete(f"{API}/delivery/zones/{za['id']}")

    def test_cart_from_demo_cannot_mix_other_tenant_item(self, menu, tenant_a_c):
        """Create cart tied to demo, try to add item id that belongs to another tenant."""
        # Create a category+item in tenant_a_c
        cat = tenant_a_c["session"].post(f"{API}/menu/categories",
                                         json={"name": "TEST_IsoCat"}).json()
        it = tenant_a_c["session"].post(f"{API}/menu/items", json={
            "category_id": cat["id"], "name": "TEST_IsoItem", "price": 1000}).json()
        # Cart on demo
        cid = requests.post(f"{API}/public/cart",
                            json={"restaurant_public_id": DEMO_PUBLIC_ID}).json()["cart_id"]
        r = requests.post(f"{API}/public/cart/{cid}/items",
                          json={"item_id": it["id"], "quantity": 1})
        assert r.status_code == 400
        tenant_a_c["session"].delete(f"{API}/menu/items/{it['id']}")
        tenant_a_c["session"].delete(f"{API}/menu/categories/{cat['id']}")
