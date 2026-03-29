# Dosya: app/main.py
import torchaudio
try:
    torchaudio.set_audio_backend("soundfile")
except:
    pass

import logging
import shutil
import os
import asyncio

from fastapi import FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import start_http_server

# --- KRİTİK: Loglama Yapılandırması (En Başta) ---
from app.core.config import settings
from app.core.logging_utils import setup_logging
setup_logging() 

from app.core.engine import tts_engine
from app.api.endpoints import router as api_router
from app.core.middleware import RequestContextMiddleware
from app.grpc_server import serve_grpc

logger = logging.getLogger("XTTS-APP")

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

for d in[UPLOAD_DIR, HISTORY_DIR, CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # [ARCH-COMPLIANCE] Log Event etiketleri
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}", extra={"event": "SERVICE_START"})
    logger.info(f"Environment: {settings.ENV} | Device: {settings.DEVICE}", extra={"event": "SERVICE_CONFIGURED"})
    
    if settings.API_KEY:
        logger.info("SECURITY: Standalone API Key protection ENABLED.", extra={"event": "SECURITY_ENABLED"})
    else:
        logger.warning("SECURITY: Running in Open/Gateway Mode (No internal auth).", extra={"event": "SECURITY_DISABLED"})

    try:
        start_http_server(settings.METRICS_PORT)
        logger.info(f"Metrics Server exposed on port {settings.METRICS_PORT}", extra={"event": "METRICS_SERVER_READY"})
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}", extra={"event": "METRICS_SERVER_ERROR"})

    try:
        logger.info("Initializing Neural Engine...", extra={"event": "MODEL_LOAD_START"})
        tts_engine.initialize()
    except Exception as e:
        logger.critical(f"CRITICAL: Engine failed to initialize: {e}", exc_info=True, extra={"event": "MODEL_LOAD_FAIL"})
        raise e

    grpc_task = asyncio.create_task(serve_grpc())
    
    yield
    
    logger.info("Shutting down...", extra={"event": "SERVICE_SHUTDOWN"})
    grpc_task.cancel()
    
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
        logger.info("Uploads cleaned.", extra={"event": "CLEANUP_COMPLETE"})

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "production" else None,
    redoc_url=None
)

Instrumentator().instrument(app)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-VCA-Chars", "X-VCA-Time", "X-VCA-RTF", "X-Trace-ID"]
)

app.include_router(api_router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

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