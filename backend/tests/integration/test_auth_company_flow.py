"""DB-backed flows: platform onboarding, admin auth, RBAC, branding/settings.

Covers Sprint 2 acceptance: US-A1.1/A1.2, US-B1.1/B1.3, US-C1.1. Runs against the
compose Postgres; skips when unreachable (see conftest).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _platform_token(api) -> str:
    r = await api.client.post(
        "/auth/login", json={"email": api.platform_email, "password": api.platform_password}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _create_company(api, token, *, slug, admin_email, cert_types=("VAT", "CT")):
    return await api.client.post(
        "/platform/companies",
        headers=_auth(token),
        json={
            "legal_name": "Itest Co LLC",
            "slug": slug,
            "primary_admin_email": admin_email,
            "enabled_cert_types": list(cert_types),
        },
    )


async def _owner_login(api, *, slug, email):
    pw = api.email.temp_password_for(email)
    assert pw, "invite email with temporary password was not captured"
    return await api.client.post("/auth/login", json={"email": email, "password": pw, "slug": slug})


# --------------------------------------------------------------------------- #
# US-A1.1 — platform creates a tenant
# --------------------------------------------------------------------------- #
async def test_platform_creates_company_and_sends_invite(api) -> None:
    token = await _platform_token(api)
    email = "owner@itest-acme.ae"
    r = await _create_company(api, token, slug="itest-acme", admin_email=email)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slug"] == "itest-acme"
    assert body["status"] == "PENDING"
    assert body["subscription_status"] == "TRIAL"
    assert body["admin_invite_sent"] is True
    assert body["enabled_cert_types"] == ["VAT", "CT"]
    assert body["portal_url"].endswith("/itest-acme")
    # Invitation email captured with credentials.
    assert api.email.temp_password_for(email) is not None

    # Duplicate slug rejected.
    dup = await _create_company(api, token, slug="itest-acme", admin_email="x@itest-acme.ae")
    assert dup.status_code == 409

    # Listing + detail.
    lst = await api.client.get("/platform/companies", headers=_auth(token))
    assert lst.status_code == 200
    assert any(c["slug"] == "itest-acme" for c in lst.json()["items"])
    detail = await api.client.get(f"/platform/companies/{body['id']}", headers=_auth(token))
    assert detail.status_code == 200


async def test_create_company_requires_platform_permission(api) -> None:
    # A company owner token must not be able to create tenants.
    token = await _platform_token(api)
    email = "owner@itest-rbac.ae"
    await _create_company(api, token, slug="itest-rbac", admin_email=email)
    owner = await _owner_login(api, slug="itest-rbac", email=email)
    owner_token = owner.json()["access_token"]
    r = await _create_company(api, owner_token, slug="itest-evil", admin_email="z@x.ae")
    assert r.status_code == 403


# --------------------------------------------------------------------------- #
# US-B1.1 — admin login (+ /me)
# --------------------------------------------------------------------------- #
async def test_company_owner_login(api) -> None:
    token = await _platform_token(api)
    email = "owner@itest-login.ae"
    await _create_company(api, token, slug="itest-login", admin_email=email)

    r = await _owner_login(api, slug="itest-login", email=email)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["principal"]["role"] == "COMPANY_OWNER"
    assert body["principal"]["company_slug"] == "itest-login"
    assert body["principal"]["company_id"]

    me = await api.client.get("/auth/me", headers=_auth(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["principal_type"] == "COMPANY"


async def test_login_rejects_bad_password(api) -> None:
    token = await _platform_token(api)
    email = "owner@itest-badpw.ae"
    await _create_company(api, token, slug="itest-badpw", admin_email=email)
    r = await api.client.post(
        "/auth/login", json={"email": email, "password": "definitely-wrong", "slug": "itest-badpw"}
    )
    assert r.status_code == 401


# --------------------------------------------------------------------------- #
# US-B1.1 — lockout after repeated failures
# --------------------------------------------------------------------------- #
async def test_login_locks_out_after_max_attempts(api) -> None:
    token = await _platform_token(api)
    email = "owner@itest-lock.ae"
    await _create_company(api, token, slug="itest-lock", admin_email=email)
    bad = {"email": email, "password": "nope", "slug": "itest-lock"}
    assert (await api.client.post("/auth/login", json=bad)).status_code == 401
    assert (await api.client.post("/auth/login", json=bad)).status_code == 401
    locked = await api.client.post("/auth/login", json=bad)  # 3rd hits the cap
    assert locked.status_code == 423
    assert "Retry-After" in locked.headers


# --------------------------------------------------------------------------- #
# US-A1.2 — suspended tenant blocks admin login
# --------------------------------------------------------------------------- #
async def test_suspended_company_blocks_login(api) -> None:
    token = await _platform_token(api)
    email = "owner@itest-susp.ae"
    created = await _create_company(api, token, slug="itest-susp", admin_email=email)
    company_id = created.json()["id"]

    # Owner can log in while active.
    assert (await _owner_login(api, slug="itest-susp", email=email)).status_code == 200

    patch = await api.client.patch(
        f"/platform/companies/{company_id}", headers=_auth(token), json={"status": "SUSPENDED"}
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "SUSPENDED"

    blocked = await _owner_login(api, slug="itest-susp", email=email)
    assert blocked.status_code == 403


# --------------------------------------------------------------------------- #
# US-C1.1 — branding (owner-only) + RBAC
# --------------------------------------------------------------------------- #
async def test_branding_update_and_rbac(api) -> None:
    token = await _platform_token(api)
    email = "owner@itest-brand.ae"
    await _create_company(api, token, slug="itest-brand", admin_email=email)
    owner_token = (await _owner_login(api, slug="itest-brand", email=email)).json()["access_token"]

    # Platform admin has no tenant scope -> 403 on tenant routes.
    assert (await api.client.get("/admin/branding", headers=_auth(token))).status_code == 403

    get_b = await api.client.get("/admin/branding", headers=_auth(owner_token))
    assert get_b.status_code == 200

    ok = await api.client.put(
        "/admin/branding",
        headers=_auth(owner_token),
        json={"primary_color": "#0F2742", "welcome_text": "Welcome to Acme"},
    )
    assert ok.status_code == 200
    assert ok.json()["primary_color"] == "#0f2742"
    assert ok.json()["welcome_text"] == "Welcome to Acme"

    bad = await api.client.put(
        "/admin/branding", headers=_auth(owner_token), json={"primary_color": "blue"}
    )
    assert bad.status_code == 422


async def test_settings_update(api) -> None:
    token = await _platform_token(api)
    email = "owner@itest-set.ae"
    await _create_company(api, token, slug="itest-set", admin_email=email)
    owner_token = (await _owner_login(api, slug="itest-set", email=email)).json()["access_token"]

    r = await api.client.put(
        "/admin/settings",
        headers=_auth(owner_token),
        json={"enabled_cert_types": ["VAT"], "overdue_after_days": 30},
    )
    assert r.status_code == 200
    assert r.json()["enabled_cert_types"] == ["VAT"]
    assert r.json()["overdue_after_days"] == 30


# --------------------------------------------------------------------------- #
# US-B1.3 — company admin user management
# --------------------------------------------------------------------------- #
async def test_user_management_and_last_owner_guard(api) -> None:
    token = await _platform_token(api)
    email = "owner@itest-users.ae"
    await _create_company(api, token, slug="itest-users", admin_email=email)
    owner_token = (await _owner_login(api, slug="itest-users", email=email)).json()["access_token"]

    # Seeded owner present.
    users = await api.client.get("/admin/users", headers=_auth(owner_token))
    assert users.status_code == 200
    assert len(users.json()) == 1
    owner_id = users.json()[0]["id"]

    # Invite a new admin.
    add = await api.client.post(
        "/admin/users",
        headers=_auth(owner_token),
        json={"email": "ops@itest-users.ae", "role": "COMPANY_ADMIN"},
    )
    assert add.status_code == 201, add.text
    assert add.json()["invite_sent"] is True
    assert len((await api.client.get("/admin/users", headers=_auth(owner_token))).json()) == 2

    # Cannot disable the last owner.
    guard = await api.client.patch(
        f"/admin/users/{owner_id}", headers=_auth(owner_token), json={"is_active": False}
    )
    assert guard.status_code == 409


# --------------------------------------------------------------------------- #
# US-B1.1 — refresh rotation + reuse detection
# --------------------------------------------------------------------------- #
async def test_refresh_rotation_and_reuse_detection(api) -> None:
    login = await api.client.post(
        "/auth/login", json={"email": api.platform_email, "password": api.platform_password}
    )
    r1 = login.json()["refresh_token"]

    rotated = await api.client.post("/auth/refresh", json={"refresh_token": r1})
    assert rotated.status_code == 200
    r2 = rotated.json()["refresh_token"]
    assert r2 != r1

    # Reusing the old (now revoked) token is treated as theft.
    reuse = await api.client.post("/auth/refresh", json={"refresh_token": r1})
    assert reuse.status_code == 401

    # The whole family is revoked, so the rotated token no longer works either.
    assert (await api.client.post("/auth/refresh", json={"refresh_token": r2})).status_code == 401
