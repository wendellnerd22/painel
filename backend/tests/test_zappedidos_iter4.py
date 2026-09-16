"""Iteration 4 backend regression: WhatsApp unified provider (WAHA/Evolution),
LAD Delivery endpoints (blocked without token), full product CRUD, webhook chats,
brute-force lockout, tenant isolation, plan limits.
"""
import os
import time
import uuid

import pytest
import requests


BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"email": "admin@zappedidos.com", "senha": "Zap@2026"}
TIMEOUT = 20


# --------------------------- fixtures ---------------------------

@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    assert s.cookies.get("zp_session")
    return s


@pytest.fixture(scope="module")
def client_store(admin_session):
    """Cria uma loja + cliente compartilhados no módulo (com token LAD placeholder)."""
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "nome": f"TEST Iter4 Loja {suffix}",
        "cliente_email": f"test-iter4-{suffix}@example.com",
        "cliente_senha": "Client@2026",
        "plano": "Essencial",
        "lad_token": "",  # começa sem token para testar 400
    }
    r = admin_session.post(f"{BASE_URL}/api/stores", json=payload, timeout=TIMEOUT)
    assert r.status_code == 201, r.text
    store = r.json()
    client = requests.Session()
    lr = client.post(f"{BASE_URL}/api/auth/login",
                     json={"email": payload["cliente_email"], "senha": payload["cliente_senha"]},
                     timeout=TIMEOUT)
    assert lr.status_code == 200, lr.text
    return {"store": store, "client_session": client, "email": payload["cliente_email"]}


# --------------------------- auth / dashboard ---------------------------

def test_login_returns_cookie_and_role():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "admin"
    assert body["email"] == ADMIN["email"]
    assert s.cookies.get("zp_session")


def test_dashboard_uses_wa_status_migrated(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/dashboard", timeout=TIMEOUT)
    assert r.status_code == 200
    data = r.json()
    assert "lojas" in data and "total" in data and "conectadas" in data
    for s in data["lojas"]:
        # migração deve garantir wa_status presente OU pelo menos ausente de waha_status legado exposto
        assert "waha_token" not in s
        assert "lad_token" not in s
        # não obrigatório todas terem wa_status (podem ser antigas), mas a chave migrada não deve quebrar


# --------------------------- store CRUD & plan limit ---------------------------

def test_create_store_and_patch_admin_fields(admin_session, client_store):
    store_id = client_store["store"]["id"]
    r = admin_session.patch(f"{BASE_URL}/api/stores/{store_id}",
                            json={"plano": "Crescimento", "status": "active"},
                            timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["plano"] == "Crescimento"


def test_client_patch_restricted_to_bot_and_lad(client_store):
    sess = client_store["client_session"]
    store_id = client_store["store"]["id"]
    # tenta mudar nome (não permitido) e bot_ativo (permitido)
    r = sess.patch(f"{BASE_URL}/api/stores/{store_id}",
                   json={"nome": "HACK NOME", "bot_ativo": False, "lad_token": "fake-token-123"},
                   timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["bot_ativo"] is False
    assert body["nome"] != "HACK NOME"


def test_plan_limit_essencial_blocks_fourth_store(admin_session):
    """Cria 3 lojas para um mesmo cliente e valida bloqueio na quarta."""
    suffix = uuid.uuid4().hex[:6]
    email = f"limit-{suffix}@example.com"
    senha = "Client@2026"
    for i in range(3):
        r = admin_session.post(f"{BASE_URL}/api/stores", json={
            "nome": f"TEST Limit {suffix} {i}",
            "cliente_email": email,
            "cliente_senha": senha,
            "plano": "Essencial",
        }, timeout=TIMEOUT)
        assert r.status_code == 201, f"loja {i}: {r.text}"
    r4 = admin_session.post(f"{BASE_URL}/api/stores", json={
        "nome": f"TEST Limit {suffix} 4",
        "cliente_email": email,
        "cliente_senha": senha,
        "plano": "Essencial",
    }, timeout=TIMEOUT)
    assert r4.status_code == 402, r4.text


def test_client_cannot_access_admin_routes(client_store):
    sess = client_store["client_session"]
    # POST /stores exige staff
    r = sess.post(f"{BASE_URL}/api/stores", json={
        "nome": "NAO", "cliente_email": "x@x.com", "cliente_senha": "x", "plano": "Essencial",
    }, timeout=TIMEOUT)
    assert r.status_code == 403


def test_client_isolation_stores_list(client_store):
    sess = client_store["client_session"]
    r = sess.get(f"{BASE_URL}/api/stores", timeout=TIMEOUT)
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert client_store["store"]["id"] in ids
    # cliente só deve ver a própria loja
    assert len(ids) == 1


# --------------------------- product CRUD ---------------------------

def test_product_full_crud(client_store):
    sess = client_store["client_session"]
    store_id = client_store["store"]["id"]

    # CREATE
    c = sess.post(f"{BASE_URL}/api/stores/{store_id}/products",
                  json={"nome": "TEST Burger", "preco": 29.9, "categoria": "Lanches"},
                  timeout=TIMEOUT)
    assert c.status_code == 201, c.text
    prod = c.json()
    assert prod["nome"] == "TEST Burger" and prod["preco"] == 29.9
    pid = prod["id"]

    # LIST contains
    lst = sess.get(f"{BASE_URL}/api/stores/{store_id}/products", timeout=TIMEOUT)
    assert lst.status_code == 200
    assert any(p["id"] == pid for p in lst.json())

    # PATCH edit
    up = sess.patch(f"{BASE_URL}/api/stores/{store_id}/products/{pid}",
                    json={"preco": 34.9, "ativo": False}, timeout=TIMEOUT)
    assert up.status_code == 200
    assert up.json()["preco"] == 34.9 and up.json()["ativo"] is False

    # Toggle ativo again
    up2 = sess.patch(f"{BASE_URL}/api/stores/{store_id}/products/{pid}",
                     json={"ativo": True}, timeout=TIMEOUT)
    assert up2.status_code == 200 and up2.json()["ativo"] is True

    # DELETE
    d = sess.delete(f"{BASE_URL}/api/stores/{store_id}/products/{pid}", timeout=TIMEOUT)
    assert d.status_code == 204

    # verify gone
    lst2 = sess.get(f"{BASE_URL}/api/stores/{store_id}/products", timeout=TIMEOUT)
    assert not any(p["id"] == pid for p in lst2.json())


# --------------------------- WhatsApp ---------------------------

def test_whatsapp_not_configured_by_default(client_store):
    sess = client_store["client_session"]
    store_id = client_store["store"]["id"]
    r = sess.get(f"{BASE_URL}/api/stores/{store_id}/whatsapp", timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_configured"
    assert body["configured"] is False
    assert body["provider"] in ("waha", "evolution")


def test_whatsapp_setup_and_qr_offline_graceful(client_store):
    sess = client_store["client_session"]
    store_id = client_store["store"]["id"]
    # setup com URL bogus (offline) — não deve 500
    setup = sess.post(f"{BASE_URL}/api/stores/{store_id}/whatsapp/setup", json={
        "provider": "waha",
        "base_url": "http://127.0.0.1:59999",  # nada escutando
        "api_token": "fake",
        "session_name": "zp_test",
    }, timeout=TIMEOUT)
    assert setup.status_code == 200, setup.text
    body = setup.json()
    assert body["provider"] == "waha"
    assert body["session"] == "zp_test"
    # status será "error" (provider offline) ou "qr_pending" — nunca 500
    assert body["status"] in {"error", "qr_pending"}

    # QR deve responder graciosamente (não 500)
    qr = sess.get(f"{BASE_URL}/api/stores/{store_id}/whatsapp/qr", timeout=TIMEOUT)
    assert qr.status_code == 200, qr.text
    qbody = qr.json()
    assert "qr" in qbody
    assert qbody["qr"] is None or isinstance(qbody["qr"], str)

    # troca para evolution — mesmo comportamento
    setup2 = sess.post(f"{BASE_URL}/api/stores/{store_id}/whatsapp/setup", json={
        "provider": "evolution",
        "base_url": "http://127.0.0.1:59998",
        "api_token": "fake",
        "session_name": "",  # deve autogerar
    }, timeout=TIMEOUT)
    assert setup2.status_code == 200
    assert setup2.json()["provider"] == "evolution"
    assert setup2.json()["session"].startswith("zp_")

    # disconnect não pode retornar 500
    disc = sess.post(f"{BASE_URL}/api/stores/{store_id}/whatsapp/disconnect", timeout=TIMEOUT)
    assert disc.status_code == 200
    assert disc.json()["status"] in {"offline", "error"}


def test_whatsapp_invalid_provider_rejected(client_store):
    sess = client_store["client_session"]
    store_id = client_store["store"]["id"]
    r = sess.post(f"{BASE_URL}/api/stores/{store_id}/whatsapp/setup", json={
        "provider": "twilio",  # not allowed
        "base_url": "http://x",
        "api_token": "x",
    }, timeout=TIMEOUT)
    assert r.status_code == 422


# --------------------------- LAD Delivery ---------------------------

def test_lad_endpoints_blocked_without_token(client_store):
    sess = client_store["client_session"]
    store_id = client_store["store"]["id"]
    # cliente removeu token (via patch anterior colocou 'fake-token-123'); vamos garantir sem token
    admin = requests.Session()
    admin.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=TIMEOUT)
    admin.patch(f"{BASE_URL}/api/stores/{store_id}", json={"lad_token": ""}, timeout=TIMEOUT)
    # após patch, campo lad_token está string vazia → deve bloquear
    for path in ("lad/loja", "lad/cardapio", "lad/cardapio/importar"):
        method = "GET" if path != "lad/cardapio/importar" else "POST"
        r = sess.request(method, f"{BASE_URL}/api/stores/{store_id}/{path}", timeout=TIMEOUT)
        assert r.status_code == 400, f"{path}: {r.status_code} {r.text}"


def test_lad_pedido_blocked_without_token_uses_idempotency(client_store):
    sess = client_store["client_session"]
    store_id = client_store["store"]["id"]
    # sem token: deve responder 400 (não 500)
    r = sess.post(f"{BASE_URL}/api/stores/{store_id}/lad/pedidos",
                  json={"payload": {"qualquer": "coisa"}}, timeout=TIMEOUT)
    assert r.status_code == 400


def test_orders_list_empty_initially(client_store):
    sess = client_store["client_session"]
    store_id = client_store["store"]["id"]
    r = sess.get(f"{BASE_URL}/api/stores/{store_id}/orders", timeout=TIMEOUT)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# --------------------------- webhook + chats ---------------------------

def test_webhook_records_chat_and_grouping(client_store):
    sess = client_store["client_session"]
    store_id = client_store["store"]["id"]
    # webhook não requer auth
    payload = {
        "event": "message",
        "payload": {"from": "5511999998888@c.us", "body": "Ola, quero pedir", "fromMe": False},
    }
    r = requests.post(f"{BASE_URL}/api/webhooks/whatsapp/{store_id}", json=payload, timeout=TIMEOUT)
    assert r.status_code == 200 and r.json().get("ok") is True

    # second message from same remote
    payload2 = {"event": "message.any", "payload": {"from": "5511999998888@c.us", "body": "Segunda", "fromMe": True}}
    requests.post(f"{BASE_URL}/api/webhooks/whatsapp/{store_id}", json=payload2, timeout=TIMEOUT)

    chats = sess.get(f"{BASE_URL}/api/stores/{store_id}/chats", timeout=TIMEOUT)
    assert chats.status_code == 200
    data = chats.json()
    remote_entries = [c for c in data if c["remote"] == "5511999998888@c.us"]
    assert len(remote_entries) == 1
    assert len(remote_entries[0]["mensagens"]) >= 2


# --------------------------- brute force lockout ---------------------------

def test_brute_force_lockout_after_five_failures():
    email = f"lockout-{uuid.uuid4().hex[:6]}@example.com"
    s = requests.Session()
    # 5 tentativas erradas
    for i in range(5):
        r = s.post(f"{BASE_URL}/api/auth/login",
                   json={"email": email, "senha": "wrong"}, timeout=TIMEOUT)
        assert r.status_code == 401, f"attempt {i}: {r.status_code}"
    # 6ª deve retornar 429 (locked)
    r6 = s.post(f"{BASE_URL}/api/auth/login",
                json={"email": email, "senha": "wrong"}, timeout=TIMEOUT)
    assert r6.status_code == 429, r6.text


# --------------------------- cleanup ---------------------------

@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_session):
    yield
    # remove lojas TEST* criadas
    r = admin_session.get(f"{BASE_URL}/api/stores", timeout=TIMEOUT)
    if r.status_code == 200:
        for s in r.json():
            if str(s.get("nome", "")).startswith("TEST"):
                admin_session.delete(f"{BASE_URL}/api/stores/{s['id']}", timeout=TIMEOUT)
