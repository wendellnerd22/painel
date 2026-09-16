import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
from lib.db import client, db, ensure_indexes


# Startup runs before the yield, shutdown after it. Add your own setup/teardown here.
@asynccontextmanager
async def lifespan(app: FastAPI):
    from lib.auth import ensure_admin_seed
    await ensure_admin_seed()
    app.state.index_task = asyncio.create_task(ensure_indexes())  # background: a big index build must not block boot
    yield
    client.close()


# Create the main app without a prefix
app = FastAPI(lifespan=lifespan)

# Configure logging (antes de qualquer uso do logger abaixo)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.get("/health")
async def health():
    from lib.db import db as _db
    try:
        await _db.command("ping")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Mongo indisponível: {exc}") from exc
    return {"status": "ok"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Include the router in the main app
from routers.auth import router as auth_router  # noqa: E402
from routers.chat import router as chat_router  # noqa: E402
from routers.motoboys import router as motoboys_router  # noqa: E402
from routers.payments import router as payments_router  # noqa: E402
from routers.rotas import router as rotas_router  # noqa: E402
from routers.stores import router as stores_router  # noqa: E402
from routers.waha import router as waha_router  # noqa: E402

api_router.include_router(auth_router)
api_router.include_router(stores_router)
api_router.include_router(payments_router)
api_router.include_router(chat_router)
api_router.include_router(waha_router)
api_router.include_router(motoboys_router)
api_router.include_router(rotas_router)

app.include_router(api_router)

_cors_env = os.environ.get('CORS_ORIGINS', '').strip()
if _cors_env:
    _cors_origins = [o.strip() for o in _cors_env.split(',') if o.strip()]
else:
    # allow_credentials=True + allow_origins=["*"] faz o Starlette refletir
    # QUALQUER origem de volta — ou seja, qualquer site na internet consegue mandar
    # requisição com o cookie de sessão do usuário. Sem CORS_ORIGINS configurado,
    # é mais seguro não liberar nenhuma origem cross-site do que liberar todas.
    _cors_origins = []
    logger.warning(
        "CORS_ORIGINS não definido — nenhuma origem cross-site será permitida. "
        "Configure CORS_ORIGINS com a URL do seu frontend em produção."
    )

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
