import logging
import shutil
import os
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.engine import tts_engine
from app.api.endpoints import router as api_router
from app.core.logging_utils import setup_logging
from app.grpc_server import serve_grpc
from app.core.config import settings

setup_logging()
logger = logging.getLogger("XTTS-APP")

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Sentiric XTTS Service (HTTP + gRPC)...")
    
    # 1. Motoru Başlat (Ağır İşlem - Warmup)
    # Model yüklenene kadar burası bloklar, bu sayede sağlık kontrolü (health check)
    # model hazır olana kadar başarısız olur. Bu istenen bir davranıştır (Readiness Probe).
    tts_engine.initialize()

    # 2. gRPC Sunucusunu Arka Planda Başlat
    grpc_task = asyncio.create_task(serve_grpc())
    
    yield
    
    logger.info("🛑 Shutting down...")
    grpc_task.cancel()
    try:
        await grpc_task
    except asyncio.CancelledError:
        pass
        
    if os.path.exists(UPLOAD_DIR): shutil.rmtree(UPLOAD_DIR)

app = FastAPI(title="Sentiric XTTS Pro", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-VCA-Chars", "X-VCA-Time", "X-VCA-RTF"] 
)

app.include_router(api_router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")