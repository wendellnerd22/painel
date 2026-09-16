import re
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from lib import traccar, waha
from lib.auth import User, optional_user
from lib.db import db
from models.schemas import Motoboy
from routers.chat import authorize

router = APIRouter(prefix="/motoboys", tags=["motoboys"])


class MotoboyRequest(BaseModel):
    nome: str
    telefone: str


def _slug(texto: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "", texto)


def _instrucoes_instalacao(unique_id: str) -> str:
    servidor = traccar.base_url() or "(peça o endereço do servidor ao seu gestor)"
    return (
        "🛵 Você foi cadastrado como entregador!\n\n"
        "Pra gente conseguir te localizar durante as entregas, instale o app gratuito "
        "*Traccar Client*:\n"
        "• Android: https://play.google.com/store/apps/details?id=org.traccar.client\n"
        "• iPhone: https://apps.apple.com/app/traccar-client/id843156974\n\n"
        "Depois de instalar, abra o app e preencha:\n"
        f"• Endereço do servidor: {servidor}\n"
        f"• Identificador do dispositivo: {unique_id}\n\n"
        "Ative o app e deixe rodando durante as entregas — é só isso, a localização "
        "aparece automaticamente pra quem acompanha o pedido."
    )


@router.post("/{store_id}", response_model=Motoboy)
async def cadastrar_motoboy(store_id: str, payload: MotoboyRequest,
                            user: Optional[User] = Depends(optional_user),
                            x_api_key: Optional[str] = Header(default=None)):
    await authorize(store_id, user, x_api_key)
    if not payload.nome.strip() or not payload.telefone.strip():
        raise HTTPException(status_code=400, detail="Nome e telefone são obrigatórios")

    motoboy = Motoboy(store_id=store_id, nome=payload.nome.strip(), telefone=payload.telefone.strip())
    unique_id = f"{store_id}-{_slug(motoboy.telefone)}"
    try:
        dispositivo = await traccar.garantir_dispositivo(unique_id, motoboy.nome)
        motoboy.traccar_device_id = dispositivo["id"]
        motoboy.traccar_unique_id = unique_id
    except traccar.TraccarError as exc:
        raise HTTPException(status_code=503, detail=f"Falha ao provisionar no Traccar: {exc}") from exc

    await db.motoboys.insert_one(motoboy.model_dump())

    try:
        await waha.send_text(session=store_id, chat_id=motoboy.telefone,
                             text=_instrucoes_instalacao(unique_id))
    except waha.WahaError:
        pass  # cadastro segue válido; o gestor pode reenviar as instruções manualmente depois

    return motoboy


@router.get("/{store_id}", response_model=List[Motoboy])
async def listar_motoboys(store_id: str, user: Optional[User] = Depends(optional_user),
                          x_api_key: Optional[str] = Header(default=None)):
    await authorize(store_id, user, x_api_key)
    docs = await db.motoboys.find({"store_id": store_id, "ativo": True}).sort("nome", 1).to_list(200)
    return [Motoboy(**d) for d in docs]


@router.post("/{store_id}/{motoboy_id}/reenviar-instrucoes")
async def reenviar_instrucoes(store_id: str, motoboy_id: str,
                              user: Optional[User] = Depends(optional_user),
                              x_api_key: Optional[str] = Header(default=None)):
    await authorize(store_id, user, x_api_key)
    doc = await db.motoboys.find_one({"store_id": store_id, "id": motoboy_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Entregador não encontrado")
    motoboy = Motoboy(**doc)
    try:
        await waha.send_text(session=store_id, chat_id=motoboy.telefone,
                             text=_instrucoes_instalacao(motoboy.traccar_unique_id or ""))
    except waha.WahaError as exc:
        raise HTTPException(status_code=503, detail=f"Falha ao enviar pelo WhatsApp: {exc}") from exc
    return {"enviado": True}


@router.delete("/{store_id}/{motoboy_id}")
async def desativar_motoboy(store_id: str, motoboy_id: str,
                            user: Optional[User] = Depends(optional_user),
                            x_api_key: Optional[str] = Header(default=None)):
    await authorize(store_id, user, x_api_key)
    await db.motoboys.update_one({"store_id": store_id, "id": motoboy_id}, {"$set": {"ativo": False}})
    return {"ok": True}
