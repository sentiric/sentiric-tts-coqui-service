import logging
import shutil
import os
import asyncio
from fastapi import FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.engine import tts_engine
from app.api.endpoints import router as api_router
from app.core.logging_utils import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.grpc_server import serve_grpc
from app.core.config import settings

setup_logging()
logger = logging.getLogger("XTTS-APP")

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

for d in [UPLOAD_DIR, HISTORY_DIR, CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"🌍 Environment: {settings.ENV} | Device: {settings.DEVICE}")
    
    if settings.API_KEY:
        logger.info("🔒 SECURITY: Standalone API Key protection ENABLED.")
    else:
        logger.info("🔓 SECURITY: Running in Open/Gateway Mode (No internal auth).")

    # 1. Motoru Başlat
    try:
        # Arka planda başlatma opsiyonu yerine bloklayıcı başlatma tercih edildi.
        # Çünkü model olmadan servis "Ready" olmamalıdır.
        tts_engine.initialize()
    except Exception as e:
        logger.critical(f"🔥 CRITICAL: Engine failed to initialize: {e}")

    # 2. gRPC Sunucusunu Başlat
    grpc_task = asyncio.create_task(serve_grpc())
    
    yield
    
    logger.info("🛑 Shutting down...")
    grpc_task.cancel()
    
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
        logger.info("🧹 Uploads cleaned.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "production" else None,
    redoc_url=None
)

# --- İZLEME ---
Instrumentator().instrument(app).expose(app)

# --- MIDDLEWARE ---
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-VCA-Chars", "X-VCA-Time", "X-VCA-RTF", "X-Trace-ID"]
)

# --- ROUTING ---
app.include_router(api_router)

# --- STATİK DOSYALAR (UI) ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# --- GELİŞMİŞ HEALTH CHECK ---
@app.get("/health")
async def health_check(response: Response):
    if not tts_engine.model:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "initializing", "detail": "Model is loading..."}
    
    return {
        "status": "healthy", 
        "version": settings.APP_VERSION,
        "device": settings.DEVICE,
        "loaded_model": settings.MODEL_NAME,
        "mode": "standalone" if settings.API_KEY else "cluster"
    }