from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from lib import orders, payments
from lib.auth import User, can_access_store, current_user, optional_user
from lib.db import db
from models.schemas import PaymentIntent

router = APIRouter(tags=["payments"])


def _mask(intent: PaymentIntent) -> PaymentIntent:
    """A intenção é consultada pelo cliente no link de pagamento (sem login),
    então nunca exponha o payload do pedido nem dados internos."""
    return intent.model_copy(update={"pedido_payload": {}})


@router.get("/payments/config")
async def payment_config():
    return {"provider": "simulado" if payments.simulado() else "mercadopago",
            "simulado": payments.simulado()}


@router.get("/payments/{intent_id}", response_model=PaymentIntent)
async def get_intent(intent_id: str):
    """Público: o cliente abre este status pelo link enviado no chat."""
    intent = await orders.load_intent(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="Cobrança não encontrada")
    return _mask(await orders.sincronizar(intent))


@router.post("/payments/{intent_id}/verificar", response_model=PaymentIntent)
async def verificar(intent_id: str):
    intent = await orders.load_intent(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="Cobrança não encontrada")
    return _mask(await orders.sincronizar(intent))


@router.post("/payments/{intent_id}/simular-aprovacao", response_model=PaymentIntent)
async def simular_aprovacao(intent_id: str):
    """Só existe no modo simulado — aprova a cobrança e libera o pedido na LAD."""
    intent = await orders.load_intent(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="Cobrança não encontrada")
    if intent.provider != "simulado":
        raise HTTPException(status_code=400,
                            detail="Cobrança real do Mercado Pago: aguarde o pagamento do cliente")
    return _mask(await orders.aprovar(intent))


@router.get("/stores/{store_id}/pagamentos", response_model=List[PaymentIntent])
async def store_payments(store_id: str, user: User = Depends(current_user)):
    if not can_access_store(user, store_id):
        raise HTTPException(status_code=403, detail="Sem acesso a esta loja")
    docs = await db.payment_intents.find({"store_id": store_id}).sort("created_at", -1).to_list(200)
    for d in docs:
        d.pop("_id", None)
    return [_mask(PaymentIntent(**d)) for d in docs]


@router.post("/webhooks/mercadopago")
async def mercadopago_webhook(
    request: Request,
    x_signature: Optional[str] = Header(default=None),
    x_request_id: Optional[str] = Header(default=None),
    data_id: Optional[str] = Query(default=None, alias="data.id"),
    tipo: Optional[str] = Query(default=None, alias="type"),
    _user: Optional[User] = Depends(optional_user),
):
    body = await request.json() if await request.body() else {}
    resource_id = data_id or str((body.get("data") or {}).get("id") or "")
    if not payments.assinatura_valida(x_signature, x_request_id, resource_id):
        raise HTTPException(status_code=401, detail="Assinatura inválida")
    evento = str(body.get("id") or f"{tipo}:{resource_id}")

    inserido = await db.webhook_events.update_one(
        {"event_key": evento}, {"$setOnInsert": {"event_key": evento, "body": body}}, upsert=True
    )
    if not inserido.upserted_id:
        return {"received": True, "duplicado": True}  # notificação reenviada

    if (tipo or body.get("type")) == "payment" and resource_id:
        try:
            status, referencia = await payments.buscar_pagamento(resource_id)
        except payments.PaymentError:
            return {"received": True, "consulta": "falhou"}
        intent = await orders.load_intent(referencia)
        if intent:
            intent.provider_payment_id = resource_id
            intent.status = status
            await orders.save_intent(intent)
            if status == payments.APROVADO:
                await orders.aprovar(intent)
    return {"received": True}
