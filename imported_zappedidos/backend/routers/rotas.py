from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from lib import traccar, waha
from lib.auth import User, optional_user
from lib.db import db
from models.schemas import Motoboy, Route
from routers.chat import authorize

router = APIRouter(prefix="/rotas", tags=["rotas"])

HORAS_VALIDADE_LINK = 4


class CriarRotaRequest(BaseModel):
    motoboy_id: str
    pedido_ids: List[str]


@router.post("/{store_id}", response_model=Route)
async def criar_rota(store_id: str, payload: CriarRotaRequest,
                     user: Optional[User] = Depends(optional_user),
                     x_api_key: Optional[str] = Header(default=None)):
    await authorize(store_id, user, x_api_key)
    if not payload.pedido_ids:
        raise HTTPException(status_code=400, detail="Selecione ao menos um pedido")

    doc_motoboy = await db.motoboys.find_one({"store_id": store_id, "id": payload.motoboy_id})
    if not doc_motoboy:
        raise HTTPException(status_code=404, detail="Entregador não encontrado — cadastre-o antes")
    motoboy = Motoboy(**doc_motoboy)
    if not motoboy.traccar_device_id:
        raise HTTPException(status_code=422, detail="Este entregador ainda não tem dispositivo Traccar provisionado")

    pedidos = await db.orders.find(
        {"store_id": store_id, "id": {"$in": payload.pedido_ids}}
    ).to_list(len(payload.pedido_ids))
    if len(pedidos) != len(payload.pedido_ids):
        raise HTTPException(status_code=404, detail="Um ou mais pedidos não encontrados nesta loja")

    try:
        tracking_url = await traccar.criar_link_rastreamento(
            motoboy.traccar_device_id, horas_validade=HORAS_VALIDADE_LINK
        )
    except traccar.TraccarError as exc:
        raise HTTPException(status_code=503, detail=f"Falha ao criar rastreamento: {exc}") from exc

    rota = Route(
        store_id=store_id, motoboy_id=motoboy.id, motoboy_nome=motoboy.nome,
        pedido_ids=payload.pedido_ids, traccar_device_id=motoboy.traccar_device_id,
        tracking_url=tracking_url,
    )
    await db.routes.insert_one(rota.model_dump())
    await db.orders.update_many(
        {"store_id": store_id, "id": {"$in": payload.pedido_ids}},
        {"$set": {"rota_id": rota.id}},
    )

    for pedido in pedidos:
        telefone = pedido.get("cliente_telefone")
        if not telefone:
            continue
        texto_cliente = (
            f"Seu pedido saiu para entrega! 🛵 Acompanhe em tempo real: {tracking_url}\n"
            f"(link válido por {HORAS_VALIDADE_LINK}h)"
        )
        try:
            await waha.send_text(session=store_id, chat_id=telefone, text=texto_cliente)
        except waha.WahaError:
            pass

    resumo_pedidos = "\n".join(
        f"• {p.get('cliente_nome') or 'Cliente'} — R$ {p.get('valor_total', 0):.2f} "
        f"(pedido {p['id'][:8]})"
        for p in pedidos
    )
    texto_motoboy = (
        f"🛵 Nova rota com {len(pedidos)} entrega(s):\n{resumo_pedidos}\n\n"
        "Mantenha o app Traccar Client aberto durante o trajeto."
    )
    try:
        await waha.send_text(session=store_id, chat_id=motoboy.telefone, text=texto_motoboy)
    except waha.WahaError:
        pass

    return rota


@router.get("/{store_id}", response_model=List[Route])
async def listar_rotas(store_id: str, user: Optional[User] = Depends(optional_user),
                       x_api_key: Optional[str] = Header(default=None)):
    await authorize(store_id, user, x_api_key)
    docs = await db.routes.find({"store_id": store_id}).sort("created_at", -1).to_list(100)
    return [Route(**d) for d in docs]
