import os
from pydantic import BaseModel

class Settings(BaseModel):
    APP_NAME: str = "Sentiric XTTS Pro"
    
    # --- MODEL & SYSTEM ---
    MODEL_NAME: str = os.getenv("TTS_COQUI_SERVICE_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")
    COQUI_TOS_AGREED: str = os.getenv("TTS_COQUI_SERVICE_TOS_AGREED", "1")
    
    # --- HARDWARE & PERFORMANCE ---
    # Varsayılanlar prodüksiyon standardına göre ayarlandı
    DEVICE: str = os.getenv("TTS_COQUI_SERVICE_DEVICE", "cuda").strip().lower()
    low_resource_raw = os.getenv("TTS_COQUI_SERVICE_LOW_RESOURCE_MODE", "true").lower()
    LOW_RESOURCE_MODE: bool = low_resource_raw == "true"
    
    # --- TORCH / INFERENCE SETTINGS ---
    use_deepspeed_raw = os.getenv("TTS_COQUI_SERVICE_ENABLE_DEEPSPEED", "false").lower()
    ENABLE_DEEPSPEED: bool = use_deepspeed_raw == "true"
    
    use_half_raw = os.getenv("TTS_COQUI_SERVICE_ENABLE_HALF_PRECISION", "true").lower()
    ENABLE_HALF_PRECISION: bool = use_half_raw == "true"

    # --- LOGGING ---
    DEBUG: bool = os.getenv("TTS_COQUI_SERVICE_DEBUG", "false").lower() == "true"

settings = Settings()