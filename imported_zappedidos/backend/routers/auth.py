from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from lib.auth import (
    COOKIE_NAME,
    TTL_DAYS,
    User,
    UserPublic,
    check_senha,
    current_user,
    make_token,
)
from lib.db import db

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_TENTATIVAS = 5
BLOQUEIO_MINUTOS = 10


class LoginRequest(BaseModel):
    email: str
    senha: str


def _public(user: User) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, nome=user.nome,
                      role=user.role, store_id=user.store_id)


@router.post("/login", response_model=UserPublic)
async def login(payload: LoginRequest, response: Response):
    email = payload.email.strip().lower()
    tentativas = await db.login_attempts.find_one({"email": email})
    agora = datetime.now(timezone.utc)
    if tentativas and tentativas.get("bloqueado_ate"):
        bloqueado_ate = tentativas["bloqueado_ate"]
        if bloqueado_ate.tzinfo is None:
            bloqueado_ate = bloqueado_ate.replace(tzinfo=timezone.utc)
        if agora < bloqueado_ate:
            raise HTTPException(
                status_code=429,
                detail=f"Muitas tentativas. Tente de novo em alguns minutos.",
            )

    doc = await db.users.find_one({"email": email})
    user = User(**doc) if doc else None
    if doc:
        doc.pop("_id", None)
    valido = user is not None and check_senha(payload.senha, user.senha_hash)

    if not valido:
        contagem = (tentativas.get("contagem", 0) if tentativas else 0) + 1
        update = {"contagem": contagem, "ultima_tentativa": agora}
        if contagem >= MAX_TENTATIVAS:
            update["bloqueado_ate"] = agora + timedelta(minutes=BLOQUEIO_MINUTOS)
            update["contagem"] = 0
        await db.login_attempts.update_one({"email": email}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    await db.login_attempts.delete_one({"email": email})
    response.set_cookie(
        COOKIE_NAME, make_token(user), httponly=True, samesite="lax",
        max_age=TTL_DAYS * 86400, path="/",
    )
    return _public(user)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return None


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(current_user)):
    return _public(user)
