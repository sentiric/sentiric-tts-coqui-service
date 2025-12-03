import os
from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- APP INFO ---
    APP_NAME: str = "Sentiric XTTS Pro"
    APP_VERSION: str = "1.2.0-stable"
    ENV: str = os.getenv("ENV", "production")
    
    # --- NETWORK & SECURITY ---
    HOST: str = "0.0.0.0"
    HTTP_PORT: int = int(os.getenv("TTS_COQUI_SERVICE_HTTP_PORT", "14030"))
    GRPC_PORT: int = int(os.getenv("TTS_COQUI_SERVICE_GRPC_PORT", "14031"))
    METRICS_PORT: int = int(os.getenv("TTS_COQUI_SERVICE_METRICS_PORT", "14032"))
    
    # CORS
    CORS_ORIGINS: List[str] = os.getenv("TTS_COQUI_SERVICE_CORS_ORIGINS", "*").split(",")

    # [YENİ] STANDALONE SECURITY
    # Eğer bu değer set edilirse, API isteklerinde 'X-API-Key' başlığı aranır.
    # Boş ise (Gateway arkasında) doğrulama yapılmaz.
    API_KEY: Optional[str] = os.getenv("TTS_COQUI_SERVICE_API_KEY", None)

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

    # --- INFERENCE DEFAULTS ---
    DEFAULT_LANGUAGE: str = os.getenv("TTS_COQUI_SERVICE_DEFAULT_LANGUAGE", "tr")
    DEFAULT_SPEAKER: str = os.getenv("TTS_COQUI_SERVICE_DEFAULT_SPEAKER", "Ana Florence")
    
    DEFAULT_TEMPERATURE: float = float(os.getenv("TTS_COQUI_SERVICE_DEFAULT_TEMPERATURE", "0.75"))
    DEFAULT_SPEED: float = float(os.getenv("TTS_COQUI_SERVICE_DEFAULT_SPEED", "1.0"))
    DEFAULT_TOP_K: int = int(os.getenv("TTS_COQUI_SERVICE_DEFAULT_TOP_K", "50"))
    DEFAULT_TOP_P: float = float(os.getenv("TTS_COQUI_SERVICE_DEFAULT_TOP_P", "0.85"))
    DEFAULT_REPETITION_PENALTY: float = float(os.getenv("TTS_COQUI_SERVICE_DEFAULT_REPETITION_PENALTY", "2.0"))
    
    DEFAULT_OUTPUT_FORMAT: str = os.getenv("TTS_COQUI_SERVICE_DEFAULT_OUTPUT_FORMAT", "wav")
    DEFAULT_SAMPLE_RATE: int = int(os.getenv("TTS_COQUI_SERVICE_DEFAULT_SAMPLE_RATE", "24000"))

    # --- LOGGING ---
    DEBUG: bool = os.getenv("TTS_COQUI_SERVICE_DEBUG", "false").lower() == "true"
    
    def __init__(self, **data):
        super().__init__(**data)
        os.environ["COQUI_TOS_AGREED"] = self.COQUI_TOS_AGREED

settings = Settings()