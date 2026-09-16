from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from lib import waha
from lib.db import db
from routers.chat import process_message
from routers.stores import get_store

router = APIRouter(prefix="/webhooks/waha", tags=["waha"])


@router.post("/{store_id}")
async def waha_webhook(
    store_id: str,
    request: Request,
    x_webhook_hmac: Optional[str] = Header(default=None),
    x_webhook_hmac_algorithm: Optional[str] = Header(default=None),
):
    """Sessão do WAHA para esta loja: nome da sessão = store_id.
    Configure o webhook dessa sessão apontando para esta URL (evento "message")."""
    raw = await request.body()
    if not waha.assinatura_valida(raw, x_webhook_hmac, x_webhook_hmac_algorithm):
        raise HTTPException(status_code=401, detail="Assinatura inválida")

    body = await request.json() if raw else {}
    evento_id = str(body.get("id") or "")
    if evento_id:
        # WAHA reenvia o mesmo evento em caso de falha/timeout — não responder 2x.
        inserido = await db.webhook_events.update_one(
            {"event_key": f"waha:{evento_id}"},
            {"$setOnInsert": {"event_key": f"waha:{evento_id}", "body": body}},
            upsert=True,
        )
        if not inserido.upserted_id:
            return {"received": True, "duplicado": True}

    if body.get("event") != "message":
        return {"received": True}

    payload = body.get("payload") or {}
    if payload.get("fromMe"):
        return {"received": True}  # eco da própria mensagem enviada pelo bot

    chat_id = payload.get("from") or ""
    texto = (payload.get("body") or "").strip()
    if not chat_id or not texto:
        return {"received": True}

    PALAVRAS_OPT_OUT = {"parar", "stop", "sair", "cancelar inscricao", "cancelar inscrição"}
    if texto.strip().lower() in PALAVRAS_OPT_OUT:
        await db.opt_outs.update_one(
            {"store_id": store_id, "chat_id": chat_id},
            {"$setOnInsert": {"store_id": store_id, "chat_id": chat_id}},
            upsert=True,
        )
        try:
            await waha.send_text(
                session=body.get("session") or store_id, chat_id=chat_id,
                text="Ok, você não vai mais receber mensagens automáticas por aqui.",
            )
        except waha.WahaError:
            pass
        return {"received": True}

    if await db.opt_outs.find_one({"store_id": store_id, "chat_id": chat_id}):
        return {"received": True}  # cliente pediu pra sair — não reengajar automaticamente

    store = await get_store(store_id)
    resposta = await process_message(store, session_id=chat_id, message=texto)

    session_name = body.get("session") or store_id
    try:
        await waha.send_text(session=session_name, chat_id=chat_id, text=resposta.reply)
    except waha.WahaError:
        pass  # a resposta já foi salva no histórico do painel; falha de rede não derruba o webhook

    return {"received": True}
