import logging
import shutil
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.engine import tts_engine
from app.core.config import settings
# Yeni Router yapısı (İleride routes.py eklenecek, şimdilik importları buradan yapalım
# ama ileride app/api/routes.py oluşturup oraya taşımak en doğrusu olur.
# Refactoring'i aşamalı yapmak adına şu anlık main.py içinde tutuyorum ama importlar temizlendi)
from app.api.endpoints import router as api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("XTTS-API")

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Engine...")
    tts_engine.initialize()
    yield
    logger.info("Shutting down...")
    if os.path.exists(UPLOAD_DIR): shutil.rmtree(UPLOAD_DIR)

app = FastAPI(title="Sentiric XTTS Ultimate", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tüm endpointleri bir router'a toplayıp ekliyoruz
app.include_router(api_router)

app.mount("/", StaticFiles(directory="static", html=True), name="static")