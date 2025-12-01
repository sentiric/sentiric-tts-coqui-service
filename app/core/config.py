import os
from pydantic import BaseModel

class Settings(BaseModel):
    APP_NAME: str = "Sentiric XTTS Pro"
    
    # --- MODEL & SYSTEM ---
    MODEL_NAME: str = os.getenv("TTS_COQUI_SERVICE_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")
    COQUI_TOS_AGREED: str = os.getenv("TTS_COQUI_SERVICE_TOS_AGREED", "1")
    
    # --- HARDWARE & PERFORMANCE ---
    DEVICE: str = os.getenv("TTS_COQUI_SERVICE_DEVICE", "cuda").strip().lower()
    LOW_RESOURCE_MODE: bool = os.getenv("TTS_COQUI_SERVICE_LOW_RESOURCE_MODE", "true").lower() == "true"
    
    # --- TORCH / INFERENCE SETTINGS ---
    ENABLE_DEEPSPEED: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_DEEPSPEED", "false").lower() == "true"
    ENABLE_HALF_PRECISION: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_HALF_PRECISION", "true").lower() == "true"
    ENABLE_ATTENTION_KV_CPU_OFFLOAD: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_ATTENTION_KV_CPU_OFFLOAD", "true").lower() == "true"
    ENABLE_STREAMING: bool = os.getenv("TTS_COQUI_SERVICE_ENABLE_STREAMING", "false").lower() == "true"

    # --- NETWORK ---
    # Governance standardına göre 14031
    GRPC_PORT: int = int(os.getenv("TTS_COQUI_SERVICE_GRPC_PORT", "14031"))

    # --- LOGGING ---
    DEBUG: bool = os.getenv("TTS_COQUI_SERVICE_DEBUG", "false").lower() == "true"
    
    def __init__(self, **data):
        super().__init__(**data)
        os.environ["COQUI_TOS_AGREED"] = self.COQUI_TOS_AGREED

settings = Settings()