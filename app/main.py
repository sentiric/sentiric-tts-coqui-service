# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI, Response  # Response'u burada import et
from pydantic import BaseModel

from app.api.v1.endpoints import router as api_v1_router
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.services.tts_service import tts_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    
    logger.info(
        "Uygulama başlıyor...", 
        project=settings.PROJECT_NAME,
        version=settings.SERVICE_VERSION,
        commit=settings.GIT_COMMIT,
        build_date=settings.BUILD_DATE,
        env=settings.ENV, 
        log_level=settings.LOG_LEVEL
    )
    
    tts_engine.load_model()
    logger.info("Uygulama hazır ve istekleri kabul ediyor.")
    yield
    logger.info("Durdurma sinyali alındı. Zarif kapanma başlıyor...")
    logger.info("Uygulama başarıyla kapatıldı.")

class AppInfo(BaseModel):
    project_name: str
    version: str
    git_commit: str
    build_date: str

app = FastAPI(title=settings.PROJECT_NAME, version=settings.SERVICE_VERSION, lifespan=lifespan)
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Health"])
def health_check():
    is_ready = tts_engine.is_ready()
    status_code = 200 if is_ready else 503
    return Response(
        status_code=status_code,
        content=f'{{"status": "ok" if is_ready else "degraded", "tts_engine_loaded": {str(is_ready).lower()}}}',
        media_type="application/json"
    )

@app.get("/info", tags=["Health"], response_model=AppInfo)
def get_app_info():
    return AppInfo(
        project_name=settings.PROJECT_NAME,
        version=settings.SERVICE_VERSION,
        git_commit=settings.GIT_COMMIT,
        build_date=settings.BUILD_DATE,
    )