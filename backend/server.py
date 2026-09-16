import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import bcrypt
import jwt
import httpx
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
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
api = APIRouter(prefix="/api")
TOKEN_COOKIE = "zp_session"


def now() -> datetime:
    return datetime.now(timezone.utc)


def clean(doc: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not doc:
        return {}
    doc = dict(doc)
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    doc.pop("waha_token", None)
    return doc


def public_user(doc: dict[str, Any]) -> dict[str, Any]:
    item = clean(doc)
    item["nome"] = item.get("nome", item.get("name", ""))
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


class ProductCreate(BaseModel):
    nome: str
    descricao: str = ""
    preco: float = Field(ge=0)
    categoria: str = "Geral"
    ativo: bool = True


class WahaSetup(BaseModel):
    base_url: str
    api_token: str
    session_name: str = ""


async def get_store(store_id: str, user: dict[str, Any]) -> dict[str, Any]:
    query: dict[str, Any] = {"id": store_id}
    if user.get("role") == "client":
        query["client_id"] = user["id"]
    store = await db.stores.find_one(query)
    if not store:
        raise HTTPException(404, "Loja não encontrada")
    store.pop("_id", None)
    return store


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
    response.set_cookie(TOKEN_COOKIE, token_for(user), httponly=True, samesite="lax", max_age=604800, path="/")
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
    stores = await db.stores.find(query, {"_id": 0, "waha_token": 0, "lad_token": 0}).to_list(500)
    connected = sum(1 for store in stores if store.get("waha_status") == "connected")
    return {"lojas": stores, "total": len(stores), "conectadas": connected, "planos": len({s.get("plano") for s in stores})}


@api.get("/plans")
async def plans(_: dict[str, Any] = Depends(current_user)):
    return [
        {"id": "essencial", "nome": "Essencial", "limite_lojas": 3, "preco": 49.9, "cor": "teal"},
        {"id": "crescimento", "nome": "Crescimento", "limite_lojas": 15, "preco": 129.9, "cor": "amber"},
        {"id": "escala", "nome": "Escala", "limite_lojas": 999, "preco": 299.9, "cor": "indigo"},
    ]


@api.get("/stores")
async def stores(user: dict[str, Any] = Depends(current_user)):
    query = {} if user.get("role") in {"admin", "reseller"} else {"client_id": user["id"]}
    docs = await db.stores.find(query, {"_id": 0, "waha_token": 0, "lad_token": 0}).sort("created_at", -1).to_list(500)
    return docs


@api.post("/stores", status_code=201)
async def create_store(body: StoreCreate, user: dict[str, Any] = Depends(staff_user)):
    client_email = body.cliente_email.strip().lower()
    existing = await db.users.find_one({"email": client_email})
    client_id = existing["id"] if existing else uuid.uuid4().hex
    if not existing:
        if not body.cliente_senha:
            raise HTTPException(400, "Informe uma senha para o cliente")
        await db.users.insert_one({"id": client_id, "email": client_email, "nome": body.nome, "role": "client", "password_hash": hash_password(body.cliente_senha), "created_at": now().isoformat()})
    store = {"id": uuid.uuid4().hex, "nome": body.nome.strip(), "cliente_email": client_email, "client_id": client_id, "plano": body.plano, "lad_token": body.lad_token, "status": "active", "bot_ativo": True, "waha_status": "not_configured", "waha_session": "", "created_at": now().isoformat()}
    await db.stores.insert_one(store)
    return clean(store)


@api.get("/stores/{store_id}")
async def store_detail(store_id: str, user: dict[str, Any] = Depends(current_user)):
    return clean(await get_store(store_id, user))


@api.patch("/stores/{store_id}")
async def update_store(store_id: str, body: StoreUpdate, user: dict[str, Any] = Depends(staff_user)):
    store = await get_store(store_id, user)
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if changes:
        await db.stores.update_one({"id": store_id}, {"$set": changes})
    store.update(changes)
    return clean(store)


@api.get("/stores/{store_id}/products")
async def products(store_id: str, user: dict[str, Any] = Depends(current_user)):
    await get_store(store_id, user)
    return await db.products.find({"store_id": store_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/stores/{store_id}/products", status_code=201)
async def create_product(store_id: str, body: ProductCreate, user: dict[str, Any] = Depends(current_user)):
    await get_store(store_id, user)
    if user.get("role") == "client" and body.preco < 0:
        raise HTTPException(400, "Preço inválido")
    product = {"id": uuid.uuid4().hex, "store_id": store_id, **body.model_dump(), "created_at": now().isoformat()}
    await db.products.insert_one(product)
    return clean(product)


@api.get("/stores/{store_id}/waha")
async def waha_status(store_id: str, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    return {"status": store.get("waha_status", "not_configured"), "session_name": store.get("waha_session", ""), "configured": bool(store.get("waha_url"))}


@api.post("/stores/{store_id}/waha/setup")
async def waha_setup(store_id: str, body: WahaSetup, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    session = body.session_name.strip() or f"zp_{store_id[:10]}"
    await db.stores.update_one({"id": store_id}, {"$set": {"waha_url": body.base_url.rstrip("/"), "waha_token": body.api_token, "waha_session": session, "waha_status": "pending"}})
    status = "pending"
    message = "Instância registrada. Inicie a sessão no WAHA para gerar o QR Code."
    try:
        async with httpx.AsyncClient(timeout=8) as http:
            result = await http.post(f"{body.base_url.rstrip('/')}/api/sessions", headers={"X-Api-Key": body.api_token}, json={"name": session, "start": True})
            if result.status_code >= 400:
                message = f"WAHA respondeu {result.status_code}; revise a URL e o token."
            else:
                status = "qr_pending"
                await db.stores.update_one({"id": store_id}, {"$set": {"waha_status": status}})
    except httpx.HTTPError:
        message = "Não foi possível alcançar o WAHA agora; a configuração foi salva para tentar novamente."
    return {"status": status, "session_name": session, "message": message}


@api.post("/stores/{store_id}/waha/test")
async def waha_test(store_id: str, user: dict[str, Any] = Depends(current_user)):
    store = await get_store(store_id, user)
    if not store.get("waha_url"):
        return {"status": "not_configured", "message": "Configure a URL e o token da instância WAHA."}
    try:
        async with httpx.AsyncClient(timeout=8) as http:
            result = await http.get(f"{store['waha_url']}/api/sessions/{store.get('waha_session')}", headers={"X-Api-Key": store.get("waha_token", "")})
        status = "connected" if result.status_code < 300 and "WORKING" in result.text.upper() else "qr_pending"
        await db.stores.update_one({"id": store_id}, {"$set": {"waha_status": status}})
        return {"status": status, "message": "Status atualizado."}
    except httpx.HTTPError:
        return {"status": "offline", "message": "WAHA não respondeu. Confira a instância na VPS."}


app = FastAPI(title="ZapPedidos API")
app.include_router(api)
origins = [x.strip() for x in os.environ.get("CORS_ORIGINS", "").split(",") if x.strip() and x.strip() != "*"]
if os.environ.get("FRONTEND_URL"):
    origins.append(os.environ["FRONTEND_URL"].rstrip("/"))
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=list(dict.fromkeys(origins)), allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.stores.create_index("id", unique=True)
    await db.login_attempts.create_index("email", unique=True)
    existing = await db.users.find_one({"email": ADMIN_EMAIL.lower()})
    if not existing:
        await db.users.insert_one({"id": uuid.uuid4().hex, "email": ADMIN_EMAIL.lower(), "nome": "Administrador Geral", "role": "admin", "password_hash": hash_password(ADMIN_PASSWORD), "created_at": now().isoformat()})
    elif not verify_password(ADMIN_PASSWORD, existing.get("password_hash", "")):
        await db.users.update_one({"email": ADMIN_EMAIL.lower()}, {"$set": {"password_hash": hash_password(ADMIN_PASSWORD), "role": "admin"}})


@app.on_event("shutdown")
async def shutdown():
    client.close()