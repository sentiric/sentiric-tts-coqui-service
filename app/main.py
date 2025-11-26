import logging
import shutil
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.engine import tts_engine
from app.api.endpoints import router as api_router
from app.core.logging_utils import setup_logging

setup_logging()
logger = logging.getLogger("XTTS-APP")

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Sentiric XTTS Service...")
    tts_engine.initialize()
    yield
    logger.info("🛑 Shutting down...")
    if os.path.exists(UPLOAD_DIR): shutil.rmtree(UPLOAD_DIR)

app = FastAPI(title="Sentiric XTTS Pro", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

# KRİTİK DÜZELTME: expose_headers eklendi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-VCA-Chars", "X-VCA-Time", "X-VCA-RTF"] 
)

app.include_router(api_router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")