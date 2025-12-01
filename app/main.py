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
from app.grpc_server import serve_grpc
from app.core.config import settings

setup_logging()
logger = logging.getLogger("XTTS-APP")

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

# Dizin temizliği ve hazırlığı
for d in [UPLOAD_DIR, HISTORY_DIR, CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"🌍 Environment: {settings.ENV} | Device: {settings.DEVICE}")
    
    # 1. Motoru Başlat (Bloklayıcı işlem - Model yüklenene kadar bekler)
    # Kubernetes için: Liveness probe hemen geçer, Readiness probe model yüklenince geçer.
    try:
        tts_engine.initialize()
    except Exception as e:
        logger.critical(f"🔥 CRITICAL: Engine failed to initialize: {e}")
        # Hata olsa bile app'i çökertmiyoruz ki logları okuyabilelim, 
        # ama /health endpoint'i 500 dönecek.

    # 2. gRPC Sunucusunu Başlat
    grpc_task = asyncio.create_task(serve_grpc())
    
    yield
    
    logger.info("🛑 Shutting down...")
    grpc_task.cancel()
    
    # Geçici dosyaları temizle
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
        logger.info("🧹 Uploads cleaned.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "production" else None, # Prod'da Swagger'ı gizle (opsiyonel)
    redoc_url=None
)

# --- İZLEME ---
Instrumentator().instrument(app).expose(app)

# --- GÜVENLİK (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-VCA-Chars", "X-VCA-Time", "X-VCA-RTF"]
)

# --- ROUTING ---
app.include_router(api_router)

# --- STATİK DOSYALAR (UI) ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# --- GELİŞMİŞ HEALTH CHECK ---
@app.get("/health")
async def health_check(response: Response):
    """
    K8s Readiness Probe için kullanılır.
    Model yüklü değilse 503 Service Unavailable döner.
    """
    if not tts_engine.model:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "initializing", "detail": "Model is loading..."}
    
    return {
        "status": "healthy", 
        "version": settings.APP_VERSION,
        "device": settings.DEVICE,
        "loaded_model": settings.MODEL_NAME
    }