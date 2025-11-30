import os
from pydantic import BaseModel

class Settings(BaseModel):
    APP_NAME: str = "Sentiric XTTS Pro"
    MODEL_NAME: str = os.getenv("TTS_COQUI_SERVICE_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")
    # FIX: Boşlukları temizle. "cuda " -> "cuda"
    DEVICE: str = os.getenv("DEVICE", "cpu").strip().lower()
    COQUI_TOS_AGREED: str = "1"
    LOW_RESOURCE_MODE: bool = os.getenv("LOW_RESOURCE_MODE", "True").lower() == "true"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

settings = Settings()