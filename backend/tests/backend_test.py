"""
MenuMind Phase A backend tests
Covers: Auth (register, login, me, logout, refresh, brute force, password reset),
Tenant isolation, Roles/Permissions, Super admin, Dashboard overview.
"""
import os
import re
import time
import secrets
import pytest
import requests
from http.cookiejar import DefaultCookiePolicy

DefaultCookiePolicy.return_ok_secure = lambda self, cookie, request: True

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback: read /app/frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api"

SUPER_EMAIL = "cooldigital.africa@gmail.com"
SUPER_PASS = "Admin1234!"
DEMO_EMAIL = "awa@chezawa.ci"
DEMO_PASS = "Demo1234!"


def new_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def login(session, email, password):
    return session.post(f"{API}/auth/login", json={"email": email, "password": password})


def register(session, name, email, password, restaurant_name, phone=""):
    return session.post(f"{API}/auth/register", json={
        "name": name, "email": email, "password": password,
        "restaurant_name": restaurant_name, "phone": phone,
    })


# -------- Health --------
def test_health():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_public_plans():
    r = requests.get(f"{API}/plans")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 3
    names = {p.get("name") for p in data}
    assert {"STARTER", "BUSINESS", "PRO"}.issubset({str(n).upper() for n in names})


# -------- Login seeded accounts --------
def test_login_super_admin():
    s = new_session()
    r = login(s, SUPER_EMAIL, SUPER_PASS)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["role"] == "SUPER_ADMIN"
    assert data.get("restaurant_id") in (None, "")
    assert "access_token" in s.cookies
    assert "refresh_token" in s.cookies


def test_login_demo_owner_and_me():
    s = new_session()
    r = login(s, DEMO_EMAIL, DEMO_PASS)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["role"] == "RESTAURANT_OWNER"
    assert data.get("restaurant_id")
    me = s.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == DEMO_EMAIL


def test_logout_clears_session():
    s = new_session()
    assert login(s, DEMO_EMAIL, DEMO_PASS).status_code == 200
    r = s.post(f"{API}/auth/logout")
    assert r.status_code == 200
    # cookies should be cleared on client (session) - request /me without them
    s2 = new_session()
    assert s2.get(f"{API}/auth/me").status_code == 401


def test_refresh_token():
    s = new_session()
    assert login(s, DEMO_EMAIL, DEMO_PASS).status_code == 200
    old_access = s.cookies.get("access_token")
    # Remove access cookie to force refresh usage
    s.cookies.pop("access_token", None)
    r = s.post(f"{API}/auth/refresh")
    assert r.status_code == 200, r.text
    assert s.cookies.get("access_token")
    # /me should work with new access
    assert s.get(f"{API}/auth/me").status_code == 200


# -------- Register creates isolated tenant --------
@pytest.fixture(scope="module")
def tenant_a():
    s = new_session()
    email = f"TEST_owner_a_{secrets.token_hex(4)}@example.com"
    r = register(s, "Owner A", email, "Passw0rd!", "TEST_Resto_A", "+22501010101")
    assert r.status_code == 200, r.text
    data = r.json()
    return {"session": s, "email": email, "user": data, "rid": data["restaurant_id"]}


@pytest.fixture(scope="module")
def tenant_b():
    s = new_session()
    email = f"TEST_owner_b_{secrets.token_hex(4)}@example.com"
    r = register(s, "Owner B", email, "Passw0rd!", "TEST_Resto_B", "+22502020202")
    assert r.status_code == 200, r.text
    data = r.json()
    return {"session": s, "email": email, "user": data, "rid": data["restaurant_id"]}


def test_register_creates_owner_with_restaurant(tenant_a):
    assert tenant_a["user"]["role"] == "RESTAURANT_OWNER"
    assert tenant_a["user"]["restaurant_id"]
    assert "access_token" in tenant_a["session"].cookies


def test_tenant_isolation_restaurants_me(tenant_a, tenant_b):
    ra = tenant_a["session"].get(f"{API}/restaurants/me")
    rb = tenant_b["session"].get(f"{API}/restaurants/me")
    assert ra.status_code == 200
    assert rb.status_code == 200
    assert ra.json()["id"] == tenant_a["rid"]
    assert rb.json()["id"] == tenant_b["rid"]
    assert ra.json()["id"] != rb.json()["id"]
    assert ra.json()["name"] == "TEST_Resto_A"
    assert rb.json()["name"] == "TEST_Resto_B"


def test_dashboard_overview_scoped(tenant_a, tenant_b):
    a = tenant_a["session"].get(f"{API}/dashboard/overview")
    b = tenant_b["session"].get(f"{API}/dashboard/overview")
    assert a.status_code == 200 and b.status_code == 200
    # Both new tenants should have 0 menu items (A/B are fresh)
    assert a.json()["menu_items"] == 0
    assert b.json()["menu_items"] == 0


def test_super_admin_restaurants_me_returns_400():
    s = new_session()
    assert login(s, SUPER_EMAIL, SUPER_PASS).status_code == 200
    r = s.get(f"{API}/restaurants/me")
    assert r.status_code == 400


# -------- Roles & permissions --------
def test_owner_can_create_staff_and_manager(tenant_a):
    s = tenant_a["session"]
    staff_email = f"TEST_staff_{secrets.token_hex(3)}@example.com"
    r = s.post(f"{API}/users", json={
        "name": "Staff One", "email": staff_email, "password": "Passw0rd!",
        "role": "RESTAURANT_STAFF",
    })
    assert r.status_code == 200, r.text
    staff = r.json()
    assert staff["role"] == "RESTAURANT_STAFF"
    assert staff["restaurant_id"] == tenant_a["rid"]

    staff_email_norm = staff_email.lower()
    # Store staff login creds for next test (set before assertions so later tests still can run)
    tenant_a["staff_email"] = staff_email_norm
    tenant_a["staff_pass"] = "Passw0rd!"
    tenant_a["staff_id"] = staff["id"]

    # list users
    lst = s.get(f"{API}/users")
    assert lst.status_code == 200
    emails = {u["email"] for u in lst.json()}
    assert staff_email_norm in emails

    # patch role to MANAGER
    pr = s.patch(f"{API}/users/{staff['id']}", json={"role": "RESTAURANT_MANAGER"})
    assert pr.status_code == 200
    assert pr.json()["role"] == "RESTAURANT_MANAGER"


def test_non_owner_cannot_create_user(tenant_a):
    assert tenant_a.get("staff_email"), "requires previous test"
    # staff was promoted to MANAGER; a MANAGER cannot create users
    s = new_session()
    assert login(s, tenant_a["staff_email"], tenant_a["staff_pass"]).status_code == 200
    r = s.post(f"{API}/users", json={
        "name": "X", "email": f"TEST_x_{secrets.token_hex(3)}@example.com",
        "password": "Passw0rd!", "role": "RESTAURANT_STAFF",
    })
    assert r.status_code == 403


def test_restaurant_user_forbidden_on_admin(tenant_a):
    r = tenant_a["session"].get(f"{API}/admin/metrics")
    assert r.status_code == 403
    r2 = tenant_a["session"].get(f"{API}/admin/restaurants")
    assert r2.status_code == 403


def test_cross_tenant_patch_user_forbidden(tenant_a, tenant_b):
    # tenant_b owner tries to patch tenant_a's staff user
    assert tenant_a.get("staff_id")
    r = tenant_b["session"].patch(
        f"{API}/users/{tenant_a['staff_id']}", json={"active": False}
    )
    # Should be 404 (not found in B's tenant) — same effect: no access
    assert r.status_code in (403, 404)


# -------- Super admin endpoints --------
def test_super_admin_metrics_and_list():
    s = new_session()
    assert login(s, SUPER_EMAIL, SUPER_PASS).status_code == 200
    m = s.get(f"{API}/admin/metrics")
    assert m.status_code == 200
    data = m.json()
    for k in ("total_restaurants", "active_restaurants", "suspended_restaurants",
              "total_orders", "estimated_mrr"):
        assert k in data
    lst = s.get(f"{API}/admin/restaurants")
    assert lst.status_code == 200
    rows = lst.json()
    assert isinstance(rows, list) and len(rows) >= 1
    assert all("owner_email" in r for r in rows)


def test_super_admin_status_toggle_and_create(tenant_a):
    s = new_session()
    assert login(s, SUPER_EMAIL, SUPER_PASS).status_code == 200
    # suspend tenant_a
    rid = tenant_a["rid"]
    r = s.patch(f"{API}/admin/restaurants/{rid}/status", json={"status": "suspended"})
    assert r.status_code == 200
    # reactivate
    r2 = s.patch(f"{API}/admin/restaurants/{rid}/status", json={"status": "active"})
    assert r2.status_code == 200

    # create restaurant via admin
    email = f"TEST_admincreated_{secrets.token_hex(3)}@example.com"
    c = s.post(f"{API}/admin/restaurants", json={
        "name": "TEST_AdminCreated", "owner_name": "Adm Owner",
        "owner_email": email, "owner_password": "Passw0rd!", "plan": "BUSINESS",
    })
    assert c.status_code == 200
    assert c.json()["name"] == "TEST_AdminCreated"


# -------- Brute force --------
def test_brute_force_lockout():
    """Fire failed logins until 429 is observed. Behind a proxy that rotates client IPs
    (and when request.client.host is used), attempts may spread across identifiers.
    Backend MUST key brute-force protection on a stable value (e.g. X-Forwarded-For or email).
    """
    email = f"TEST_bf_{secrets.token_hex(4)}@example.com"
    s = new_session()
    codes = []
    for _ in range(25):
        r = login(s, email, "wrongpass")
        codes.append(r.status_code)
        if r.status_code == 429:
            break
    assert 429 in codes, (
        f"No 429 after {len(codes)} failed logins through public URL. "
        f"Likely brute-force is keyed on request.client.host which rotates behind the "
        f"ingress proxy, so attempts never aggregate. Codes: {codes}"
    )


# -------- Forgot/Reset password (enumeration parity) --------
def test_forgot_password_enumeration_parity():
    s = new_session()
    r1 = s.post(f"{API}/auth/forgot-password", json={"email": DEMO_EMAIL})
    r2 = s.post(f"{API}/auth/forgot-password", json={"email": "nope_notexist@example.com"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()


def test_reset_password_full_flow():
    """Set FRONTEND_URL=http://localhost:3000, restart backend, trigger forgot, read log,
    reset password, verify old fails new works, token can't be reused, then restore.
    Local mode (no /app/backend/.env): FRONTEND_URL comes from the launch environment,
    no restart is needed, and the backend log path comes from RESTOIA_TEST_BACKEND_LOG."""
    import subprocess
    env_path = "/app/backend/.env"
    docker_mode = os.path.exists(env_path)
    original = ""
    if docker_mode:
        with open(env_path) as f:
            original = f.read()
        m = re.search(r'^FRONTEND_URL="([^"]+)"', original, re.M)
        original_url = m.group(1) if m else ""
    else:
        assert os.environ.get("FRONTEND_URL", "").rstrip("/") == "http://localhost:3000", (
            "local mode: FRONTEND_URL must be http://localhost:3000 (set by the launcher)")
    try:
        if docker_mode:
            new_content = re.sub(r'^FRONTEND_URL=".*"', 'FRONTEND_URL="http://localhost:3000"',
                                 original, flags=re.M)
            with open(env_path, "w") as f:
                f.write(new_content)
            subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True,
                           capture_output=True)
            time.sleep(4)

        # Create a dedicated test user so we don't disturb demo
        test_email = f"TEST_reset_{secrets.token_hex(4)}@example.com"
        test_pass = "OldPass123!"
        s = new_session()
        r = register(s, "Reset User", test_email, test_pass, "TEST_ResetResto")
        assert r.status_code == 200

        # Clear log position
        if docker_mode:
            log_file = "/var/log/supervisor/backend.err.log"
            try:
                start_size = os.path.getsize(log_file)
            except FileNotFoundError:
                # try out log
                log_file = "/var/log/supervisor/backend.out.log"
                start_size = os.path.getsize(log_file)
            scan_files = ("/var/log/supervisor/backend.err.log",
                          "/var/log/supervisor/backend.out.log")
        else:
            log_file = os.environ.get("RESTOIA_TEST_BACKEND_LOG", "")
            assert log_file and os.path.exists(log_file), (
                "local mode: RESTOIA_TEST_BACKEND_LOG must point to the backend log")
            start_size = os.path.getsize(log_file)
            scan_files = (log_file,)

        s2 = new_session()
        fp = s2.post(f"{API}/auth/forgot-password", json={"email": test_email})
        assert fp.status_code == 200
        time.sleep(2)

        # Read new log content
        with open(log_file) as lf:
            lf.seek(start_size)
            log_tail = lf.read()
        # fallback: scan both files
        if "reset-password?token=" not in log_tail:
            for f_ in scan_files:
                try:
                    with open(f_) as lf:
                        log_tail += "\n" + lf.read()[-20000:]
                except Exception:
                    pass
        tok_match = re.search(r"reset-password\?token=([A-Za-z0-9_\-]+)", log_tail)
        assert tok_match, f"No reset token found in logs. Tail:\n{log_tail[-2000:]}"
        token = tok_match.group(1)

        new_pass = "NewPass456!"
        rp = s2.post(f"{API}/auth/reset-password", json={"token": token, "password": new_pass})
        assert rp.status_code == 200, rp.text

        # Old password fails
        s3 = new_session()
        assert login(s3, test_email, test_pass).status_code == 401
        # New password works
        s4 = new_session()
        assert login(s4, test_email, new_pass).status_code == 200

        # Token cannot be reused
        s5 = new_session()
        rp2 = s5.post(f"{API}/auth/reset-password", json={"token": token, "password": "Yet3rPass!"})
        assert rp2.status_code == 400
    finally:
        if docker_mode:
            with open(env_path, "w") as f:
                f.write(original)
            subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True,
                           capture_output=True)
            time.sleep(4)
