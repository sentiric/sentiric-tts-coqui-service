# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel # Pydantic BaseModel'i import edelim

from app.api.v1.endpoints import router as api_v1_router
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.services.tts_service import tts_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    
    # --- YENİ: ZENGİNLEŞTİRİLMİŞ BAŞLANGIÇ LOGU ---
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
    # Burada gerekirse veritabanı bağlantılarını kapatma gibi işlemler yapılabilir.
    logger.info("Uygulama başarıyla kapatıldı.")


# --- YENİ: BİLGİ ENDPOINT'İ İÇİN RESPONSE MODELİ ---
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
    # Kubernetes gibi sistemlerin anlayabilmesi için HTTP status code'unu değiştirmek daha iyi bir pratik
    return Response(
        status_code=status_code,
        content={"status": "ok" if is_ready else "degraded", "details": {"tts_engine_loaded": is_ready}}
    )

# --- YENİ: UYGULAMA BİLGİLERİNİ SUNAN ENDPOINT ---
@app.get("/info", tags=["Health"], response_model=AppInfo)
def get_app_info():
    """Uygulamanın versiyon ve build bilgilerini döndürür."""
    return AppInfo(
        project_name=settings.PROJECT_NAME,
        version=settings.SERVICE_VERSION,
        git_commit=settings.GIT_COMMIT,
        build_date=settings.BUILD_DATE,
    )