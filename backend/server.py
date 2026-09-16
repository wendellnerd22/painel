"""ZapPedidos backend — painel unificado (admin + cliente) com WhatsApp WAHA/Evolution e API LAD Delivery."""
import base64
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import bcrypt
import httpx
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "zap-pedidos-local-secret-change-me")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@zappedidos.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Zap@2026")
LAD_BASE_URL = os.environ.get("LAD_BASE_URL", "https://api2.laddelivery.com.br").rstrip("/")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
api = APIRouter(prefix="/api")
TOKEN_COOKIE = "zp_session"

# Planos disponíveis (limite de lojas por cliente + preço mensal referência)
PLANS = [
    {"id": "essencial", "nome": "Essencial", "limite_lojas": 3, "preco": 49.9, "cor": "teal"},
    {"id": "crescimento", "nome": "Crescimento", "limite_lojas": 15, "preco": 129.9, "cor": "amber"},
    {"id": "escala", "nome": "Escala", "limite_lojas": 999, "preco": 299.9, "cor": "indigo"},
]
PLAN_BY_NAME = {p["nome"]: p for p in PLANS}


# ============================================================ helpers

def now() -> datetime:
    return datetime.now(timezone.utc)


def clean(doc: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not doc:
        return {}
    doc = dict(doc)
    for secret in ("_id", "password_hash", "waha_token", "evolution_token", "lad_token"):
        doc.pop(secret, None)
    return doc


def public_user(doc: dict[str, Any]) -> dict[str, Any]:
    item = clean(doc)
    item["nome"] = item.get("nome") or item.get("name", "")
    return item


def hash_password(value: str) -> str:
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()


def verify_password(value: str, hashed: str) -> bool:
    return bcrypt.checkpw(value.encode(), hashed.encode())


def token_for(user: dict[str, Any]) -> str:
    payload = {"sub": user["id"], "exp": now() + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(TOKEN_COOKIE)
    if not token:
        raise HTTPException(401, "Sessão expirada")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Sessão inválida") from exc
    user = await db.users.find_one({"id": payload.get("sub")})
    if not user:
        raise HTTPException(401, "Usuário não encontrado")
    return user


async def staff_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") not in {"admin", "reseller"}:
        raise HTTPException(403, "Acesso restrito ao painel administrativo")
    return user


async def get_store(store_id: str, user: dict[str, Any]) -> dict[str, Any]:
    query: dict[str, Any] = {"id": store_id}
    if user.get("role") == "client":
        query["client_id"] = user["id"]
    store = await db.stores.find_one(query)
    if not store:
        raise HTTPException(404, "Loja não encontrada")
    store.pop("_id", None)
    return store


# ============================================================ pydantic

class Login(BaseModel):
    email: str
    senha: str


class StoreCreate(BaseModel):
    nome: str
    cliente_email: str
    cliente_senha: str = ""
    plano: str = "Essencial"
    lad_token: str = ""


class StoreUpdate(BaseModel):
    nome: Optional[str] = None
    plano: Optional[str] = None
    status: Optional[str] = None
    bot_ativo: Optional[bool] = None
    lad_token: Optional[str] = None


class ProductCreate(BaseModel):
    nome: str
    descricao: str = ""
    preco: float = Field(ge=0)
    categoria: str = "Geral"
    ativo: bool = True


class ProductUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    preco: Optional[float] = Field(default=None, ge=0)
    categoria: Optional[str] = None
    ativo: Optional[bool] = None


class WhatsAppSetup(BaseModel):
    provider: str = Field(default="waha", pattern="^(waha|evolution)$")
    base_url: str
    api_token: str
    session_name: str = ""


# ============================================================ WhatsApp providers

class WhatsAppProvider:
    """Abstração para WAHA e Evolution API, ambos self-hosted."""

    def __init__(self, provider: str, base_url: str, token: str, session: str):
        self.provider = provider
        self.base = base_url.rstrip("/")
        self.token = token
        self.session = session

    @classmethod
    def from_store(cls, store: dict[str, Any]) -> Optional["WhatsAppProvider"]:
        if not store.get("wa_url") or not store.get("wa_session"):
            return None
        return cls(
            provider=store.get("wa_provider") or "waha",
            base_url=store["wa_url"],
            token=store.get("wa_token") or "",
            session=store["wa_session"],
        )

    def _headers(self) -> dict[str, str]:
        if self.provider == "evolution":
            return {"apikey": self.token, "Content-Type": "application/json"}
        return {"X-Api-Key": self.token, "Content-Type": "application/json"}

    async def start_session(self) -> dict[str, Any]:
        """Cria/inicia a sessão. Retorna dict com status e mensagem legível."""
        async with httpx.AsyncClient(timeout=15) as http:
            if self.provider == "evolution":
                # POST /instance/create — se já existe, apenas conecta
                r = await http.post(
                    f"{self.base}/instance/create",
                    headers=self._headers(),
                    json={
                        "instanceName": self.session,
                        "qrcode": True,
                        "integration": "WHATSAPP-BAILEYS",
                    },
                )
                if r.status_code in (403, 409):
                    # instância já existe → prossegue para /connect
                    return {"status": "qr_pending", "message": "Instância já existente. Buscando QR code..."}
                if r.status_code >= 400:
                    return {"status": "error", "message": f"Evolution respondeu {r.status_code}: {r.text[:200]}"}
                return {"status": "qr_pending", "message": "Instância criada. Escaneie o QR code."}
            # WAHA
            r = await http.post(
                f"{self.base}/api/sessions",
                headers=self._headers(),
                json={"name": self.session, "start": True},
            )
            if r.status_code in (409, 422):
                return {"status": "qr_pending", "message": "Sessão já existente. Buscando QR code..."}
            if r.status_code >= 400:
                return {"status": "error", "message": f"WAHA respondeu {r.status_code}: {r.text[:200]}"}
            return {"status": "qr_pending", "message": "Sessão iniciada. Escaneie o QR code."}

    async def get_qr(self) -> dict[str, Any]:
        """Retorna { qr: 'data:image/png;base64,...' } ou { qr: None, message }"""
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                if self.provider == "evolution":
                    r = await http.get(f"{self.base}/instance/connect/{self.session}", headers=self._headers())
                    if r.status_code >= 400:
                        return {"qr": None, "message": f"Evolution não retornou o QR (HTTP {r.status_code})."}
                    data = r.json() if r.text else {}
                    base64_qr = (
                        (data.get("base64") if isinstance(data, dict) else None)
                        or (data.get("qrcode", {}).get("base64") if isinstance(data.get("qrcode"), dict) else None)
                        or data.get("code")
                    )
                    if not base64_qr:
                        return {"qr": None, "message": "Aguardando QR code do WhatsApp..."}
                    if not base64_qr.startswith("data:"):
                        base64_qr = f"data:image/png;base64,{base64_qr}"
                    return {"qr": base64_qr, "message": "QR code atualizado."}
                # WAHA — GET /api/{session}/auth/qr?format=image → JSON com base64 data
                r = await http.get(
                    f"{self.base}/api/{self.session}/auth/qr",
                    headers={**self._headers(), "Accept": "application/json"},
                    params={"format": "image"},
                )
                if r.status_code == 422:
                    return {"qr": None, "message": "Sessão ainda inicializando. Aguarde alguns segundos."}
                if r.status_code >= 400:
                    return {"qr": None, "message": f"WAHA não retornou o QR (HTTP {r.status_code})."}
                try:
                    data = r.json()
                    base64_qr = data.get("data") or data.get("qr")
                    mime = data.get("mimetype", "image/png")
                    if base64_qr:
                        return {"qr": f"data:{mime};base64,{base64_qr}", "message": "QR code atualizado."}
                except Exception:
                    if r.headers.get("content-type", "").startswith("image/"):
                        b64 = base64.b64encode(r.content).decode()
                        return {"qr": f"data:{r.headers['content-type']};base64,{b64}", "message": "QR code atualizado."}
                return {"qr": None, "message": "Aguardando QR code..."}
        except httpx.HTTPError as exc:
            return {"qr": None, "message": f"Provider offline: {exc}"}

    async def status(self) -> dict[str, Any]:
        """Retorna status normalizado: connected | qr_pending | offline | error."""
        async with httpx.AsyncClient(timeout=10) as http:
            try:
                if self.provider == "evolution":
                    r = await http.get(f"{self.base}/instance/connectionState/{self.session}", headers=self._headers())
                    if r.status_code == 404:
                        return {"status": "not_started", "raw": "instance_not_found"}
                    if r.status_code >= 400:
                        return {"status": "error", "raw": f"HTTP {r.status_code}"}
                    data = r.json()
                    state = (data.get("instance", {}).get("state") or data.get("state") or "").lower()
                    mapping = {"open": "connected", "connecting": "qr_pending", "close": "offline", "refused": "offline"}
                    return {"status": mapping.get(state, "qr_pending"), "raw": state}
                # WAHA
                r = await http.get(f"{self.base}/api/sessions/{self.session}", headers=self._headers())
                if r.status_code == 404:
                    return {"status": "not_started", "raw": "session_not_found"}
                if r.status_code >= 400:
                    return {"status": "error", "raw": f"HTTP {r.status_code}"}
                data = r.json()
                state = (data.get("status") or "").upper()
                mapping = {
                    "WORKING": "connected",
                    "SCAN_QR_CODE": "qr_pending",
                    "STARTING": "qr_pending",
                    "FAILED": "offline",
                    "STOPPED": "offline",
                }
                return {"status": mapping.get(state, "qr_pending"), "raw": state}
            except httpx.HTTPError as exc:
                return {"status": "offline", "raw": str(exc)}

    async def logout(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as http:
            try:
                if self.provider == "evolution":
                    await http.delete(f"{self.base}/instance/logout/{self.session}", headers=self._headers())
                else:
                    await http.post(f"{self.base}/api/sessions/{self.session}/stop", headers=self._headers())
                return {"status": "offline", "message": "Sessão desconectada."}
            except httpx.HTTPError as exc:
                return {"status": "error", "message": f"Falha ao desconectar: {exc}"}


# ============================================================ LAD client

class LadClient:
    def __init__(self, token: str):
        self.token = token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> Any:
        async with httpx.AsyncClient(timeout=20) as http:
            try:
                r = await http.request(method, f"{LAD_BASE_URL}{path}", headers=self._headers(), json=json_body)
            except httpx.HTTPError as exc:
                raise HTTPException(503, f"Falha de rede ao contatar a API LAD: {exc}") from exc
        if r.status_code >= 400:
            try:
                body = r.json()
                msg = body.get("descricao") or body.get("titulo") or r.text
            except Exception:
                msg = r.text or f"Erro HTTP {r.status_code}"
            raise HTTPException(r.status_code, f"LAD: {msg}")
        return r.json()

    async def loja(self):
        return await self._request("GET", "/v1/loja")

    async def cardapio(self):
        return await self._request("GET", "/v1/cardapio")

    async def frete(self, payload: dict):
        return await self._request("POST", "/v1/frete", payload)

    async def criar_pedido(self, payload: dict):
        return await self._request("POST", "/v1/pedidos", payload)

    async def pedido(self, uuid_: str):
        return await self._request("GET", f"/v1/pedidos/{uuid_}")


async def ensure_plan_limit(client_id: str, plano: str):
    """Bloqueia criação quando o cliente estoura o limite de lojas do plano."""
    plan = PLAN_BY_NAME.get(plano)
    if not plan:
        return
    count = await db.stores.count_documents({"client_id": client_id})
    if count >= plan["limite_lojas"]:
        raise HTTPException(
            402,
            f"Plano {plano} permite até {plan['limite_lojas']} lojas. Faça upgrade para adicionar mais.",
        )


# ============================================================ endpoints

@api.get("/")
async def root():
    return {"message": "ZapPedidos API", "status": "online"}


@api.get("/health")
async def health():
    await db.command("ping")
    return {"status": "ok"}


@api.post("/auth/login")
async def login(body: Login, response: Response):
    email = body.email.strip().lower()
    attempt = await db.login_attempts.find_one({"email": email})
    if attempt and attempt.get("locked_until"):
        locked_until = datetime.fromisoformat(attempt["locked_until"])
        if locked_until > now():
            raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.senha, user["password_hash"]):
        count = (attempt or {}).get("count", 0) + 1
        update: dict[str, Any] = {"count": count, "last_attempt": now().isoformat()}
        if count >= 5:
            update["count"] = 0
            update["locked_until"] = (now() + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({"email": email}, {"$set": update}, upsert=True)
        raise HTTPException(401, "E-mail ou senha inválidos")
    await db.login_attempts.delete_one({"email": email})
    response.set_cookie(TOKEN_COOKIE, token_for(user), httponly=True, samesite="lax", max_age=604800, path="/", secure=True)
    return public_user(user)


@api.post("/auth/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(TOKEN_COOKIE, path="/")


@api.get("/auth/me")
async def me(user: dict[str, Any] = Depends(current_user)):
    return public_user(user)


@api.get("/dashboard")
async def dashboard(user: dict[str, Any] = Depends(current_user)):
    query = {} if user.get("role") in {"admin", "reseller"} else {"client_id": user["id"]}
    stores = await db.stores.find(query, {"_id": 0, "wa_token": 0, "lad_token": 0}).to_list(500)
    connected = sum(1 for s in stores if s.get("wa_status") == "connected")
    return {
        "lojas": stores,
        "total": len(stores),
        "conectadas": connected,
        "planos": len({s.get("plano") for s in stores if s.get("plano")}),
    }


@api.get("/plans")
async def plans(_: dict[str, Any] = Depends(current_user)):
    return PLANS


@api.get("/stores")
async def stores(user: dict[str, Any] = Depends(current_user)):
    query = {} if user.get("role") in {"admin", "reseller"} else {"client_id": user["id"]}
    docs = await db.stores.find(query, {"_id": 0, "wa_token": 0, "lad_token": 0}).sort("created_at", -1).to_list(500)
    return docs


@api.post("/stores", status_code=201)
async def create_store(body: StoreCreate, user: dict[str, Any] = Depends(staff_user)):
    client_email = body.cliente_email.strip().lower()
    existing = await db.users.find_one({"email": client_email})
    client_id = existing["id"] if existing else uuid.uuid4().hex
    if not existing:
        if not body.cliente_senha:
            raise HTTPException(400, "Informe uma senha para o cliente")
        await db.users.insert_one({
            "id": client_id,
            "email": client_email,
            "nome": body.nome,
            "role": "client",
            "password_hash": hash_password(body.cliente_senha),
            "created_at": now().isoformat(),
        })
    await ensure_plan_limit(client_id, body.plano)
    store = {
        "id": uuid.uuid4().hex,
        "nome": body.nome.strip(),
        "cliente_email": client_email,
        "client_id": client_id,
        "plano": body.plano,
        "lad_token": body.lad_token,
        "status": "active",
        "bot_ativo": True,
        "wa_provider": "waha",
        "wa_status": "not_configured",
        "wa_session": "",
        "created_at": now().isoformat(),
    }
    await db.stores.insert_one(store)
    return clean(store)


@api.get("/stores/{store_id}")
async def store_detail(store_id: str, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    result = clean(store)
    # Expose helpful non-secret flags to the UI
    result["has_lad_token"] = bool(store.get("lad_token"))
    result["has_wa_config"] = bool(store.get("wa_url"))
    return result


@api.patch("/stores/{store_id}")
async def update_store(store_id: str, body: StoreUpdate, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    # Cliente só pode mudar bot_ativo e lad_token da própria loja
    if user.get("role") == "client":
        changes = {k: v for k, v in changes.items() if k in {"bot_ativo", "lad_token"}}
    if changes:
        await db.stores.update_one({"id": store_id}, {"$set": changes})
    store.update(changes)
    return clean(store)


@api.delete("/stores/{store_id}", status_code=204)
async def delete_store(store_id: str, user: dict[str, Any] = Depends(staff_user)):
    await get_store(store_id, user)
    await db.stores.delete_one({"id": store_id})
    await db.products.delete_many({"store_id": store_id})
    await db.orders.delete_many({"store_id": store_id})


# ---------------------- catálogo (CRUD completo) ----------------------

@api.get("/stores/{store_id}/products")
async def products_list(store_id: str, user: dict[str, Any] = Depends(current_user)):
    await get_store(store_id, user)
    return await db.products.find({"store_id": store_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/stores/{store_id}/products", status_code=201)
async def create_product(store_id: str, body: ProductCreate, user: dict[str, Any] = Depends(current_user)):
    await get_store(store_id, user)
    product = {"id": uuid.uuid4().hex, "store_id": store_id, **body.model_dump(), "created_at": now().isoformat()}
    await db.products.insert_one(product)
    return clean(product)


@api.patch("/stores/{store_id}/products/{product_id}")
async def update_product(store_id: str, product_id: str, body: ProductUpdate, user: dict[str, Any] = Depends(current_user)):
    await get_store(store_id, user)
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(400, "Nada para atualizar")
    result = await db.products.update_one({"id": product_id, "store_id": store_id}, {"$set": changes})
    if not result.matched_count:
        raise HTTPException(404, "Produto não encontrado")
    doc = await db.products.find_one({"id": product_id}, {"_id": 0})
    return clean(doc)


@api.delete("/stores/{store_id}/products/{product_id}", status_code=204)
async def delete_product(store_id: str, product_id: str, user: dict[str, Any] = Depends(current_user)):
    await get_store(store_id, user)
    result = await db.products.delete_one({"id": product_id, "store_id": store_id})
    if not result.deleted_count:
        raise HTTPException(404, "Produto não encontrado")


# ---------------------- WhatsApp (WAHA / Evolution) ----------------------

@api.get("/stores/{store_id}/whatsapp")
async def whatsapp_state(store_id: str, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    provider = WhatsAppProvider.from_store(store)
    if not provider:
        return {
            "status": store.get("wa_status", "not_configured"),
            "provider": store.get("wa_provider", "waha"),
            "session": "",
            "configured": False,
        }
    state = await provider.status()
    if state["status"] not in ("error", "not_started"):
        await db.stores.update_one({"id": store_id}, {"$set": {"wa_status": state["status"]}})
    return {
        "status": state["status"],
        "raw": state.get("raw"),
        "provider": provider.provider,
        "session": provider.session,
        "configured": True,
    }


@api.post("/stores/{store_id}/whatsapp/setup")
async def whatsapp_setup(store_id: str, body: WhatsAppSetup, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    session = body.session_name.strip() or f"zp_{store_id[:10]}"
    await db.stores.update_one({"id": store_id}, {"$set": {
        "wa_provider": body.provider,
        "wa_url": body.base_url.rstrip("/"),
        "wa_token": body.api_token,
        "wa_session": session,
        "wa_status": "pending",
    }})
    provider = WhatsAppProvider(body.provider, body.base_url, body.api_token, session)
    result = await provider.start_session()
    await db.stores.update_one({"id": store_id}, {"$set": {"wa_status": result["status"]}})
    return {**result, "provider": body.provider, "session": session}


@api.get("/stores/{store_id}/whatsapp/qr")
async def whatsapp_qr(store_id: str, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    provider = WhatsAppProvider.from_store(store)
    if not provider:
        raise HTTPException(400, "Configure primeiro a URL e o token do WhatsApp.")
    # Consulta status antes; se já conectado devolve nulo
    state = await provider.status()
    if state["status"] == "connected":
        await db.stores.update_one({"id": store_id}, {"$set": {"wa_status": "connected"}})
        return {"qr": None, "status": "connected", "message": "WhatsApp já conectado."}
    qr = await provider.get_qr()
    return {**qr, "status": state["status"]}


@api.post("/stores/{store_id}/whatsapp/disconnect")
async def whatsapp_disconnect(store_id: str, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    provider = WhatsAppProvider.from_store(store)
    if not provider:
        raise HTTPException(400, "Nenhuma instância configurada.")
    result = await provider.logout()
    await db.stores.update_one({"id": store_id}, {"$set": {"wa_status": "offline"}})
    return result


# ---------------------- LAD Delivery v1 ----------------------

async def _lad_for(store: dict[str, Any]) -> LadClient:
    token = store.get("lad_token")
    if not token:
        raise HTTPException(400, "Cadastre o token LAD Delivery nas configurações da loja.")
    return LadClient(token)


@api.get("/stores/{store_id}/lad/loja")
async def lad_loja(store_id: str, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    lad = await _lad_for(store)
    return await lad.loja()


@api.get("/stores/{store_id}/lad/cardapio")
async def lad_cardapio(store_id: str, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    lad = await _lad_for(store)
    return await lad.cardapio()


@api.post("/stores/{store_id}/lad/cardapio/importar")
async def lad_import_catalog(store_id: str, user: dict[str, Any] = Depends(current_user)):
    """Baixa o cardápio LAD e cria/atualiza os produtos locais."""
    store = await get_store(store_id, user)
    lad = await _lad_for(store)
    data = await lad.cardapio()
    inserted = 0
    updated = 0
    for cat in data.get("categorias", []):
        for prod in cat.get("produtos", []):
            lad_id = str(prod["id"])
            payload = {
                "store_id": store_id,
                "nome": prod.get("nome", ""),
                "descricao": prod.get("descricao") or "",
                "preco": float(prod.get("preco") or 0),
                "categoria": cat.get("nome") or "Geral",
                "ativo": True,
                "lad_id": lad_id,
                "imagem_url": prod.get("imagemUrl"),
            }
            existing = await db.products.find_one({"store_id": store_id, "lad_id": lad_id})
            if existing:
                await db.products.update_one({"id": existing["id"]}, {"$set": payload})
                updated += 1
            else:
                payload.update({"id": uuid.uuid4().hex, "created_at": now().isoformat()})
                await db.products.insert_one(payload)
                inserted += 1
    return {"importados": inserted, "atualizados": updated, "categorias": len(data.get("categorias", []))}


class FretePayload(BaseModel):
    endereco: dict[str, Any]


@api.post("/stores/{store_id}/lad/frete")
async def lad_frete(store_id: str, body: FretePayload, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    lad = await _lad_for(store)
    return await lad.frete(body.model_dump())


class PedidoPayload(BaseModel):
    payload: dict[str, Any]


@api.post("/stores/{store_id}/lad/pedidos")
async def lad_criar_pedido(store_id: str, body: PedidoPayload, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    lad = await _lad_for(store)
    payload = dict(body.payload or {})
    payload.setdefault("idempotencyKey", uuid.uuid4().hex)
    resposta = await lad.criar_pedido(payload)
    # Registra localmente para exibir no painel
    await db.orders.insert_one({
        "id": uuid.uuid4().hex,
        "store_id": store_id,
        "uuid_lad": resposta.get("uuid"),
        "status": resposta.get("status", {}).get("descricao", "pendente"),
        "valor_total": resposta.get("valorTotal"),
        "tipo": resposta.get("tipo"),
        "itens": resposta.get("itens", []),
        "pagamento": resposta.get("pagamento", {}),
        "raw": resposta,
        "created_at": now().isoformat(),
    })
    return resposta


@api.get("/stores/{store_id}/orders")
async def list_orders(store_id: str, user: dict[str, Any] = Depends(current_user)):
    await get_store(store_id, user)
    docs = await db.orders.find({"store_id": store_id}, {"_id": 0, "raw": 0}).sort("created_at", -1).to_list(200)
    return docs


@api.post("/stores/{store_id}/orders/{order_id}/refresh")
async def refresh_order(store_id: str, order_id: str, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    lad = await _lad_for(store)
    order = await db.orders.find_one({"id": order_id, "store_id": store_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if not order.get("uuid_lad"):
        return {"status": order.get("status")}
    resposta = await lad.pedido(order["uuid_lad"])
    await db.orders.update_one({"id": order_id}, {"$set": {
        "status": resposta.get("status", {}).get("descricao", order.get("status")),
        "raw": resposta,
    }})
    return resposta


# ---------------------- webhooks WAHA / Evolution (recebem mensagens) ----------------------

@api.post("/webhooks/whatsapp/{store_id}")
async def whatsapp_webhook(store_id: str, request: Request):
    """Grava mensagens recebidas para exibir no painel Conversas."""
    payload = await request.json()
    event = payload.get("event") or payload.get("type") or "message"
    body = payload.get("payload") or payload.get("data") or payload
    remote = (
        body.get("from")
        or body.get("chatId")
        or body.get("key", {}).get("remoteJid")
        or "desconhecido"
    )
    text = (
        body.get("body")
        or body.get("text")
        or body.get("message", {}).get("conversation")
        or ""
    )
    if event and "message" in str(event).lower():
        await db.chats.insert_one({
            "id": uuid.uuid4().hex,
            "store_id": store_id,
            "remote": remote,
            "text": text,
            "from_me": bool(body.get("fromMe") or body.get("key", {}).get("fromMe")),
            "created_at": now().isoformat(),
        })
    return {"ok": True}


@api.get("/stores/{store_id}/chats")
async def list_chats(store_id: str, user: dict[str, Any] = Depends(current_user)):
    await get_store(store_id, user)
    docs = await db.chats.find({"store_id": store_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    # Agrupa por remote
    grouped: dict[str, dict[str, Any]] = {}
    for msg in docs:
        key = msg["remote"]
        entry = grouped.setdefault(key, {"remote": key, "ultima": msg["text"], "quando": msg["created_at"], "mensagens": []})
        entry["mensagens"].append(msg)
    return list(grouped.values())


# ============================================================ app bootstrap

app = FastAPI(title="ZapPedidos API")
app.include_router(api)

origins = [x.strip() for x in os.environ.get("CORS_ORIGINS", "").split(",") if x.strip() and x.strip() != "*"]
if os.environ.get("FRONTEND_URL"):
    origins.append(os.environ["FRONTEND_URL"].rstrip("/"))
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=list(dict.fromkeys(origins)),
    allow_origin_regex=r"https://.*",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.stores.create_index("id", unique=True)
    await db.products.create_index([("store_id", 1), ("id", 1)])
    await db.orders.create_index([("store_id", 1), ("created_at", -1)])
    await db.chats.create_index([("store_id", 1), ("created_at", -1)])
    await db.login_attempts.create_index("email", unique=True)
    # Migração dos campos legados waha_* → wa_*
    await db.stores.update_many(
        {"waha_status": {"$exists": True}, "wa_status": {"$exists": False}},
        [{"$set": {
            "wa_status": "$waha_status",
            "wa_url": {"$ifNull": ["$waha_url", ""]},
            "wa_token": {"$ifNull": ["$waha_token", ""]},
            "wa_session": {"$ifNull": ["$waha_session", ""]},
            "wa_provider": {"$ifNull": ["$wa_provider", "waha"]},
        }}],
    )
    existing = await db.users.find_one({"email": ADMIN_EMAIL.lower()})
    if not existing:
        await db.users.insert_one({
            "id": uuid.uuid4().hex,
            "email": ADMIN_EMAIL.lower(),
            "nome": "Administrador Geral",
            "role": "admin",
            "password_hash": hash_password(ADMIN_PASSWORD),
            "created_at": now().isoformat(),
        })
    elif not verify_password(ADMIN_PASSWORD, existing.get("password_hash", "")):
        await db.users.update_one({"email": ADMIN_EMAIL.lower()}, {"$set": {
            "password_hash": hash_password(ADMIN_PASSWORD), "role": "admin",
        }})


@app.on_event("shutdown")
async def shutdown():
    client.close()
