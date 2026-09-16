from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from lib import bot
from lib.auth import User, can_access_store, optional_user
from lib.db import db
from models.schemas import ChatMessage, ChatRequest, ChatResponse, OrderRecord, ToolTrace
from routers.stores import client_for, get_store

router = APIRouter(prefix="/chat", tags=["chat"])


async def authorize(store_id: str, user: Optional[User], api_key: Optional[str]):
    """Painel: sessão com acesso à loja. Conector WhatsApp: header X-API-Key da loja."""
    store = await get_store(store_id)
    if user is not None and can_access_store(user, store_id):
        return store
    if api_key and store.api_key and api_key == store.api_key:
        return store
    raise HTTPException(status_code=401, detail="Sem acesso a esta loja")


def _session_key(store_id: str, session_id: str) -> str:
    return f"{store_id}:{session_id}"


@router.get("/{store_id}/{session_id}", response_model=List[ChatMessage])
async def history(store_id: str, session_id: str,
                  user: Optional[User] = Depends(optional_user),
                  x_api_key: Optional[str] = Header(default=None)):
    await authorize(store_id, user, x_api_key)
    docs = await db.chat_messages.find(
        {"store_id": store_id, "session_id": session_id}
    ).sort("created_at", 1).to_list(500)
    for d in docs:
        d.pop("_id", None)
    return [ChatMessage(**d) for d in docs]


@router.delete("/{store_id}/{session_id}", status_code=204)
async def reset(store_id: str, session_id: str,
                user: Optional[User] = Depends(optional_user),
                x_api_key: Optional[str] = Header(default=None)):
    await authorize(store_id, user, x_api_key)
    await db.chat_messages.delete_many({"store_id": store_id, "session_id": session_id})
    bot.reset_session(_session_key(store_id, session_id))
    return None


async def process_message(store, session_id: str, message: str) -> ChatResponse:
    """Núcleo do atendimento: usado pelo endpoint HTTP (painel/simulador) e pelo
    webhook do conector de WhatsApp (ex.: WAHA) — a resposta é idêntica nos dois casos."""
    store_id = store.id
    lad = client_for(store)

    system_message = bot.BASE_PROMPT.format(
        nome_loja=store.nome,
        extra=f"\nInstruções extras do lojista: {store.bot_prompt}" if store.bot_prompt.strip() else "",
    )
    key = _session_key(store_id, session_id)

    user_msg = ChatMessage(session_id=session_id, store_id=store_id,
                           role="user", text=message.strip())
    await db.chat_messages.insert_one(user_msg.model_dump())

    try:
        ctx = bot.BotContext(store=store, session_id=session_id, lad=lad)
        text, traces, pedido, intent_id = await bot.run_turn(
            key, system_message, ctx, message.strip()
        )
    except Exception as exc:  # noqa: BLE001
        detalhe = str(exc)
        intent_id = None
        if "Budget has been exceeded" in detalhe or "RateLimitError" in detalhe:
            text = ("Estou temporariamente fora do ar: os créditos da chave de IA (Emergent LLM Key) "
                    "acabaram. Recarregue os créditos no painel da Emergent para o bot voltar a atender.")
        else:
            text = f"Não consegui responder agora ({detalhe[:160]}). Tente novamente em instantes."
        traces = [{"name": "erro_ia", "ok": False, "resumo": detalhe[:180]}]
        pedido = None

    bot_msg = ChatMessage(session_id=session_id, store_id=store_id, role="bot",
                          text=text, tools=[ToolTrace(**t) for t in traces])
    await db.chat_messages.insert_one(bot_msg.model_dump())

    order_uuid = None
    if pedido and pedido.get("uuid"):
        order_uuid = pedido["uuid"]
        status = pedido.get("status") or {}
        cliente = pedido.get("cliente") or {}
        record = OrderRecord(
            id=order_uuid, store_id=store_id, session_id=session_id,
            cliente_nome=cliente.get("nome", ""), cliente_telefone=cliente.get("telefone", ""),
            tipo=pedido.get("tipo", "DELIVERY"),
            status_codigo=status.get("codigo", "E"),
            status_descricao=status.get("descricao", "Pendente"),
            valor_total=float(pedido.get("valorTotal") or 0),
            data_pedido=str(pedido.get("dataPedido") or ""),
            demo=store.demo or not store.token,
            payload=pedido,
        )
        await db.orders.update_one({"id": order_uuid}, {"$set": record.model_dump()}, upsert=True)

    return ChatResponse(reply=text, tools=[ToolTrace(**t) for t in traces],
                        order_uuid=order_uuid, payment_intent_id=intent_id)


@router.post("/{store_id}", response_model=ChatResponse)
async def send(store_id: str, payload: ChatRequest,
               user: Optional[User] = Depends(optional_user),
               x_api_key: Optional[str] = Header(default=None)):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Mensagem vazia")
    store = await authorize(store_id, user, x_api_key)
    return await process_message(store, payload.session_id, payload.message)
