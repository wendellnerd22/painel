from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import User, admin_user, can_access_store, current_user, hash_senha
from lib.auth import User as AuthUser
from lib.db import db
from lib.lad import LadClient, LadError
from models.schemas import (
    ConnectionResult,
    OrderRecord,
    Store,
    StoreCreate,
    StoreUpdate,
)

router = APIRouter(prefix="/stores", tags=["stores"])


async def get_store(store_id: str) -> Store:
    doc = await db.stores.find_one({"id": store_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    doc.pop("_id", None)
    return Store(**doc)


async def store_for_user(store_id: str, user: AuthUser = Depends(current_user)) -> Store:
    if not can_access_store(user, store_id):
        raise HTTPException(status_code=403, detail="Sem acesso a esta loja")
    return await get_store(store_id)


def visible(store: Store, user: AuthUser) -> Store:
    """O lojista nunca vê o token LAD nem a chave de API da integração."""
    if user.role == "admin":
        return store
    return store.model_copy(update={"token": "", "api_key": ""})


def client_for(store: Store) -> LadClient:
    return LadClient(token=store.token, demo=store.demo or not store.token)


async def _probe(store: Store) -> ConnectionResult:
    try:
        loja = await client_for(store).loja()
    except LadError as exc:
        return ConnectionResult(ok=False, mensagem=f"[{exc.status}] {exc.descricao}")
    return ConnectionResult(
        ok=True,
        mensagem="Modo demonstração ativo" if (store.demo or not store.token) else "Token válido, loja conectada",
        nome_loja=loja.get("nome"),
        aberta_agora=loja.get("abertaAgora"),
    )


async def _upsert_lojista(store: Store, email: Optional[str], senha: Optional[str]) -> None:
    email = (email or "").strip().lower()
    if not email:
        return
    existing = await db.users.find_one({"email": email})
    if existing and existing.get("store_id") not in (None, store.id):
        raise HTTPException(status_code=400, detail="Este e-mail já pertence a outro usuário")
    if existing:
        changes: dict[str, Any] = {"store_id": store.id, "role": "lojista", "nome": store.nome}
        if senha:
            changes["senha_hash"] = hash_senha(senha)
        await db.users.update_one({"email": email}, {"$set": changes})
        return
    if not senha:
        raise HTTPException(status_code=400, detail="Defina uma senha para o acesso do lojista")
    novo = User(email=email, nome=store.nome, role="lojista", store_id=store.id,
                senha_hash=hash_senha(senha))
    await db.users.insert_one(novo.model_dump())


@router.get("", response_model=List[Store])
async def list_stores(user: AuthUser = Depends(current_user)):
    query = {} if user.role == "admin" else {"id": user.store_id or "__none__"}
    docs = await db.stores.find(query).sort("created_at", 1).to_list(200)
    for d in docs:
        d.pop("_id", None)
    return [visible(Store(**d), user) for d in docs]


@router.post("", response_model=Store, status_code=201)
async def create_store(payload: StoreCreate, user: AuthUser = Depends(admin_user)):
    if not payload.nome.strip():
        raise HTTPException(status_code=400, detail="Informe o nome da loja")
    data = payload.model_dump()
    email = data.pop("lojista_email", "")
    senha = data.pop("lojista_senha", "")
    store = Store(**data, lojista_email=(email or "").strip().lower())
    probe = await _probe(store)
    store.conexao_ok = probe.ok
    store.conexao_msg = probe.mensagem
    await db.stores.insert_one(store.model_dump())
    await _upsert_lojista(store, email, senha)
    return store


@router.get("/{store_id}", response_model=Store)
async def read_store(store_id: str, user: AuthUser = Depends(current_user)):
    store = await store_for_user(store_id, user)
    return visible(store, user)


@router.patch("/{store_id}", response_model=Store)
async def update_store(store_id: str, payload: StoreUpdate, user: AuthUser = Depends(current_user)):
    store = await store_for_user(store_id, user)
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    email = changes.pop("lojista_email", None)
    senha = changes.pop("lojista_senha", None)
    if user.role != "admin":
        # o lojista só ajusta as instruções do bot
        changes = {k: v for k, v in changes.items() if k == "bot_prompt"}
        email = senha = None
    updated = store.model_copy(update=changes)
    if email is not None:
        updated.lojista_email = email.strip().lower()
    probe = await _probe(updated)
    updated.conexao_ok = probe.ok
    updated.conexao_msg = probe.mensagem
    await db.stores.update_one({"id": store_id}, {"$set": updated.model_dump()})
    if user.role == "admin":
        await _upsert_lojista(updated, email, senha)
    return visible(updated, user)


@router.delete("/{store_id}", status_code=204)
async def delete_store(store_id: str, user: AuthUser = Depends(admin_user)):
    await get_store(store_id)
    await db.stores.delete_one({"id": store_id})
    await db.chat_messages.delete_many({"store_id": store_id})
    await db.users.delete_many({"store_id": store_id, "role": "lojista"})
    return None


@router.post("/{store_id}/testar", response_model=ConnectionResult)
async def test_connection(store_id: str, user: AuthUser = Depends(current_user)):
    store = await store_for_user(store_id, user)
    probe = await _probe(store)
    await db.stores.update_one(
        {"id": store_id}, {"$set": {"conexao_ok": probe.ok, "conexao_msg": probe.mensagem}}
    )
    return probe


@router.get("/{store_id}/loja")
async def store_info(store_id: str, user: AuthUser = Depends(current_user)) -> Any:
    store = await store_for_user(store_id, user)
    try:
        return await client_for(store).loja()
    except LadError as exc:
        raise HTTPException(status_code=502, detail=exc.descricao) from exc


@router.get("/{store_id}/cardapio")
async def store_menu(store_id: str, user: AuthUser = Depends(current_user)) -> Any:
    store = await store_for_user(store_id, user)
    try:
        return await client_for(store).cardapio()
    except LadError as exc:
        raise HTTPException(status_code=502, detail=exc.descricao) from exc


@router.get("/{store_id}/pedidos", response_model=List[OrderRecord])
async def store_orders(store_id: str, user: AuthUser = Depends(current_user)):
    await store_for_user(store_id, user)
    docs = await db.orders.find({"store_id": store_id}).sort("created_at", -1).to_list(200)
    for d in docs:
        d.pop("_id", None)
    return [OrderRecord(**d) for d in docs]


@router.post("/{store_id}/pedidos/{uuid_}/atualizar", response_model=OrderRecord)
async def refresh_order(store_id: str, uuid_: str, user: AuthUser = Depends(current_user)):
    store = await store_for_user(store_id, user)
    doc = await db.orders.find_one({"store_id": store_id, "id": uuid_})
    if not doc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    doc.pop("_id", None)
    record = OrderRecord(**doc)
    try:
        pedido = await client_for(store).pedido(uuid_)
    except LadError as exc:
        if record.demo:
            return record
        raise HTTPException(status_code=502, detail=exc.descricao) from exc
    status = pedido.get("status") or {}
    record.status_codigo = status.get("codigo", record.status_codigo)
    record.status_descricao = status.get("descricao", record.status_descricao)
    record.valor_total = pedido.get("valorTotal", record.valor_total)
    record.payload = pedido
    await db.orders.update_one({"id": uuid_}, {"$set": record.model_dump()})
    return record
