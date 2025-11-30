import os
from pydantic import BaseModel

class Settings(BaseModel):
    APP_NAME: str = "Sentiric XTTS Pro"
    
    # --- MODEL & SYSTEM ---
    MODEL_NAME: str = os.getenv("TTS_COQUI_SERVICE_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")
    COQUI_TOS_AGREED: str = os.getenv("TTS_COQUI_SERVICE_TOS_AGREED", "1")
    
    # --- HARDWARE & PERFORMANCE ---
    DEVICE: str = os.getenv("TTS_COQUI_SERVICE_DEVICE", "cuda").strip().lower()
    
    # DÜZELTME: Ara değişken (raw) kullanmadan direkt atama yapıyoruz.
    LOW_RESOURCE_MODE: bool = os.getenv("TTS_COQUI_SERVICE_LOW_RESOURCE_MODE", "true").lower() == "true"
    
    # --- TORCH / INFERENCE SETTINGS ---
    ENABLE_DEEPSPEED: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_DEEPSPEED", "false").lower() == "true"
    ENABLE_HALF_PRECISION: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_HALF_PRECISION", "true").lower() == "true"
    
    # .env dosyasında eklediğimiz yeni ayarları da buraya ekleyelim
    ENABLE_ATTENTION_KV_CPU_OFFLOAD: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_ATTENTION_KV_CPU_OFFLOAD", "true").lower() == "true"
    ENABLE_STREAMING: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_STREAMING", "false").lower() == "true"

    # --- LOGGING ---
    DEBUG: bool = os.getenv("TTS_COQUI_SERVICE_DEBUG", "false").lower() == "true"
    
    def __init__(self, **data):
        super().__init__(**data)
        # KÜTÜPHANE UYUMLULUĞU İÇİN (CRITICAL FIX)
        # TTS kütüphanesi doğrudan os.environ['COQUI_TOS_AGREED'] okuyor.
        os.environ["COQUI_TOS_AGREED"] = self.COQUI_TOS_AGREED

settings = Settings()