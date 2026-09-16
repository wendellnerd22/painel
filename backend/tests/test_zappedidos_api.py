import os
import uuid

import pytest
import requests


BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"email": "admin@zappedidos.com", "senha": "Zap@2026"}


@pytest.fixture
def admin():
    session = requests.Session()
    response = session.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert response.status_code == 200
    assert session.cookies.get("zp_session")
    return session


def test_health_and_unauthenticated_protection():
    health = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert health.status_code == 200 and health.json()["status"] == "ok"
    me = requests.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert me.status_code == 401


def test_admin_session_and_logout():
    session = requests.Session()
    login = session.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert login.status_code == 200
    assert login.json()["role"] == "admin"
    me = session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert me.status_code == 200 and me.json()["email"] == ADMIN["email"]
    assert session.post(f"{BASE_URL}/api/auth/logout", timeout=15).status_code == 204
    assert session.get(f"{BASE_URL}/api/auth/me", timeout=15).status_code == 401


def test_store_client_isolation_catalog_and_waha(admin):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "nome": f"TEST Loja {suffix}",
        "cliente_email": f"test-{suffix}@example.com",
        "cliente_senha": "Client@2026",
        "plano": "Essencial",
    }
    created = admin.post(f"{BASE_URL}/api/stores", json=payload, timeout=15)
    assert created.status_code == 201
    store = created.json()
    assert store["nome"] == payload["nome"] and "waha_token" not in store
    store_id = store["id"]
    client = requests.Session()
    assert client.post(f"{BASE_URL}/api/auth/login", json={"email": payload["cliente_email"], "senha": payload["cliente_senha"]}, timeout=15).status_code == 200
    visible = client.get(f"{BASE_URL}/api/stores", timeout=15)
    assert visible.status_code == 200 and [x["id"] for x in visible.json()] == [store_id]
    product = client.post(f"{BASE_URL}/api/stores/{store_id}/products", json={"nome": "TEST X", "preco": 19.9}, timeout=15)
    assert product.status_code == 201 and product.json()["nome"] == "TEST X"
    waha = client.get(f"{BASE_URL}/api/stores/{store_id}/waha", timeout=15)
    assert waha.status_code == 200 and waha.json()["status"] == "not_configured"
    assert client.post(f"{BASE_URL}/api/stores/{store_id}/waha/test", timeout=15).json()["status"] == "not_configured"


def test_plans_and_admin_dashboard(admin):
    plans = admin.get(f"{BASE_URL}/api/plans", timeout=15)
    assert plans.status_code == 200 and len(plans.json()) == 3
    dashboard = admin.get(f"{BASE_URL}/api/dashboard", timeout=15)
    assert dashboard.status_code == 200
    assert all("waha_token" not in store for store in dashboard.json()["lojas"])