"""Iter 6 - Mercado Pago per-store integration tests.

Verifies:
- POST /stores/{id}/mercadopago/setup encrypts & never returns token; GET stores/{id} exposes has_mp_token=true
- GET /stores/{id}/mercadopago returns configured/ambiente
- DELETE removes token
- /pix and /checkout without token => 400 with clear message
- /pix and /checkout with an invalid dummy token => 401/400 forwarded from MP (never 500)
- /pagamentos returns list
- POST /webhooks/mercadopago/{id} always responds 200
- Dashboard and stores listing never expose mp_token_enc
- clean() also strips mp_token_enc (verified via store_detail)
- Isolation: client cannot configure MP for another store (404)
"""
import os
import uuid

import pytest
import requests


BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"email": "admin@zappedidos.com", "senha": "Zap@2026"}
TIMEOUT = 25
# TEST- token that MP will 401 back
DUMMY_TOKEN = "TEST-1234567890-invalidtoken-abcdef0123456789"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def store_and_client(admin):
    suffix = uuid.uuid4().hex[:8]
    email = f"test-mp-{suffix}@example.com"
    senha = "Client@2026"
    payload = {
        "nome": f"TEST MP Loja {suffix}",
        "cliente_email": email,
        "cliente_senha": senha,
        "plano": "Essencial",
    }
    r = admin.post(f"{BASE_URL}/api/stores", json=payload, timeout=TIMEOUT)
    assert r.status_code == 201, r.text
    store = r.json()

    client = requests.Session()
    lr = client.post(f"{BASE_URL}/api/auth/login", json={"email": email, "senha": senha}, timeout=TIMEOUT)
    assert lr.status_code == 200, lr.text
    return {"store": store, "client": client, "email": email}


# ---------- second store owned by another client (for isolation test)
@pytest.fixture(scope="module")
def other_store(admin):
    suffix = uuid.uuid4().hex[:8]
    email = f"test-mp-other-{suffix}@example.com"
    payload = {
        "nome": f"TEST MP Outra {suffix}",
        "cliente_email": email,
        "cliente_senha": "Client@2026",
        "plano": "Essencial",
    }
    r = admin.post(f"{BASE_URL}/api/stores", json=payload, timeout=TIMEOUT)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- MP status default
def test_mp_status_default_false(store_and_client):
    sess = store_and_client["client"]
    sid = store_and_client["store"]["id"]
    r = sess.get(f"{BASE_URL}/api/stores/{sid}/mercadopago", timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert body["ambiente"] in ("producao", "teste")


def test_mp_pix_without_token_returns_400(store_and_client):
    sess = store_and_client["client"]
    sid = store_and_client["store"]["id"]
    r = sess.post(f"{BASE_URL}/api/stores/{sid}/mercadopago/pix",
                  json={"valor": 1.0, "descricao": "teste", "email_pagador": "x@x.com"},
                  timeout=TIMEOUT)
    assert r.status_code == 400, r.text
    assert "Mercado Pago" in r.json().get("detail", "") or "Access Token" in r.json().get("detail", "")


def test_mp_checkout_without_token_returns_400(store_and_client):
    sess = store_and_client["client"]
    sid = store_and_client["store"]["id"]
    r = sess.post(f"{BASE_URL}/api/stores/{sid}/mercadopago/checkout",
                  json={"itens": [{"titulo": "Prod", "quantidade": 1, "preco_unitario": 10.0}]},
                  timeout=TIMEOUT)
    assert r.status_code == 400, r.text


def test_mp_pagamentos_empty_initially(store_and_client):
    sess = store_and_client["client"]
    sid = store_and_client["store"]["id"]
    r = sess.get(f"{BASE_URL}/api/stores/{sid}/mercadopago/pagamentos", timeout=TIMEOUT)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- setup token
def test_mp_setup_encrypts_and_never_returns_token(store_and_client):
    sess = store_and_client["client"]
    sid = store_and_client["store"]["id"]
    r = sess.post(f"{BASE_URL}/api/stores/{sid}/mercadopago/setup",
                  json={"access_token": DUMMY_TOKEN, "ambiente": "teste"},
                  timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    # never returns the actual token
    assert DUMMY_TOKEN not in str(body)
    assert body.get("ambiente") == "teste"

    # GET status now configured true
    st = sess.get(f"{BASE_URL}/api/stores/{sid}/mercadopago", timeout=TIMEOUT).json()
    assert st["configured"] is True
    assert st["ambiente"] == "teste"

    # store detail should expose has_mp_token and NOT mp_token_enc
    det = sess.get(f"{BASE_URL}/api/stores/{sid}", timeout=TIMEOUT).json()
    assert det.get("has_mp_token") is True
    assert "mp_token_enc" not in det
    assert DUMMY_TOKEN not in str(det)


def test_dashboard_and_stores_list_never_leak_mp_token(admin, store_and_client):
    sid = store_and_client["store"]["id"]
    d = admin.get(f"{BASE_URL}/api/dashboard", timeout=TIMEOUT).json()
    assert "mp_token_enc" not in str(d)
    lst = admin.get(f"{BASE_URL}/api/stores", timeout=TIMEOUT).json()
    for s in lst:
        assert "mp_token_enc" not in s


def test_mp_pix_with_invalid_token_returns_mp_error_not_500(store_and_client):
    sess = store_and_client["client"]
    sid = store_and_client["store"]["id"]
    r = sess.post(f"{BASE_URL}/api/stores/{sid}/mercadopago/pix",
                  json={"valor": 1.0, "descricao": "teste iter6", "email_pagador": "pagador@example.com"},
                  timeout=TIMEOUT)
    # MP will 400/401 on invalid token; must be forwarded, never 500
    assert r.status_code in (400, 401, 403), f"got {r.status_code}: {r.text}"
    assert "Mercado Pago" in r.json().get("detail", "")


def test_mp_checkout_with_invalid_token_returns_mp_error_not_500(store_and_client):
    sess = store_and_client["client"]
    sid = store_and_client["store"]["id"]
    r = sess.post(f"{BASE_URL}/api/stores/{sid}/mercadopago/checkout",
                  json={"itens": [{"titulo": "X", "quantidade": 1, "preco_unitario": 5.0}]},
                  timeout=TIMEOUT)
    assert r.status_code in (400, 401, 403), f"got {r.status_code}: {r.text}"


# ---------- webhook always 200
def test_mp_webhook_no_body_returns_200(store_and_client):
    sid = store_and_client["store"]["id"]
    r = requests.post(f"{BASE_URL}/api/webhooks/mercadopago/{sid}", timeout=TIMEOUT)
    assert r.status_code == 200


def test_mp_webhook_unknown_store_returns_200():
    r = requests.post(f"{BASE_URL}/api/webhooks/mercadopago/unknown-store-id", timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json().get("received") is False


def test_mp_webhook_with_payment_topic_but_bad_token_returns_200(store_and_client):
    sid = store_and_client["store"]["id"]
    r = requests.post(f"{BASE_URL}/api/webhooks/mercadopago/{sid}",
                      json={"type": "payment", "data": {"id": "999999"}}, timeout=TIMEOUT)
    assert r.status_code == 200


# ---------- isolation
def test_client_cannot_configure_mp_for_other_store(store_and_client, other_store):
    sess = store_and_client["client"]
    other_id = other_store["id"]
    r = sess.post(f"{BASE_URL}/api/stores/{other_id}/mercadopago/setup",
                  json={"access_token": DUMMY_TOKEN, "ambiente": "teste"},
                  timeout=TIMEOUT)
    assert r.status_code == 404, r.text


# ---------- delete removes
def test_mp_delete_removes_token(store_and_client):
    sess = store_and_client["client"]
    sid = store_and_client["store"]["id"]
    r = sess.delete(f"{BASE_URL}/api/stores/{sid}/mercadopago", timeout=TIMEOUT)
    assert r.status_code == 204
    st = sess.get(f"{BASE_URL}/api/stores/{sid}/mercadopago", timeout=TIMEOUT).json()
    assert st["configured"] is False
    det = sess.get(f"{BASE_URL}/api/stores/{sid}", timeout=TIMEOUT).json()
    assert det.get("has_mp_token") is False


# ---------- cleanup
@pytest.fixture(scope="module", autouse=True)
def cleanup(admin):
    yield
    r = admin.get(f"{BASE_URL}/api/stores", timeout=TIMEOUT)
    if r.status_code == 200:
        for s in r.json():
            if str(s.get("nome", "")).startswith("TEST"):
                admin.delete(f"{BASE_URL}/api/stores/{s['id']}", timeout=TIMEOUT)
