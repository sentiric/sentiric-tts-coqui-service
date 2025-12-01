import os
from typing import List
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- APP INFO ---
    APP_NAME: str = "Sentiric XTTS Pro"
    APP_VERSION: str = "1.2.0"
    ENV: str = os.getenv("ENV", "production")
    
    # --- MODEL & SYSTEM ---
    MODEL_NAME: str = os.getenv("TTS_COQUI_SERVICE_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")
    COQUI_TOS_AGREED: str = os.getenv("TTS_COQUI_SERVICE_TOS_AGREED", "1")
    
    # --- HARDWARE & PERFORMANCE ---
    DEVICE: str = os.getenv("TTS_COQUI_SERVICE_DEVICE", "cuda").strip().lower()
    LOW_RESOURCE_MODE: bool = os.getenv("TTS_COQUI_SERVICE_LOW_RESOURCE_MODE", "true").lower() == "true"
    
    # --- TORCH SETTINGS ---
    ENABLE_DEEPSPEED: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_DEEPSPEED", "false").lower() == "true"
    ENABLE_HALF_PRECISION: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_HALF_PRECISION", "true").lower() == "true"
    ENABLE_ATTENTION_KV_CPU_OFFLOAD: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_ATTENTION_KV_CPU_OFFLOAD", "true").lower() == "true"
    ENABLE_STREAMING: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_STREAMING", "false").lower() == "true"

    # --- NETWORK & SECURITY ---
    # Docker içinde dinlenecek host (Genellikle 0.0.0.0)
    HOST: str = "0.0.0.0"
    # Konteyner içi HTTP portu (Dışarıya mapping ile açılır)
    HTTP_PORT: int = int(os.getenv("TTS_COQUI_SERVICE_HTTP_PORT", "14030"))
    GRPC_PORT: int = int(os.getenv("TTS_COQUI_SERVICE_GRPC_PORT", "14031"))
    
    # CORS Güvenliği: Virgülle ayrılmış domain listesi
    # Örn: http://localhost:3000,https://dashboard.sentiric.cloud
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    # --- LOGGING ---
    DEBUG: bool = os.getenv("TTS_COQUI_SERVICE_DEBUG", "false").lower() == "true"
    
    def __init__(self, **data):
        super().__init__(**data)
        os.environ["COQUI_TOS_AGREED"] = self.COQUI_TOS_AGREED

settings = Settings()