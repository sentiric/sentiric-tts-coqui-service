import os
from pydantic import BaseModel

class Settings(BaseModel):
    APP_NAME: str = "Sentiric XTTS Pro"
    MODEL_NAME: str = os.getenv("TTS_COQUI_SERVICE_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")
    DEVICE: str = "cuda" if os.getenv("CUDA_VISIBLE_DEVICES") else "cpu"
    COQUI_TOS_AGREED: str = "1"
    LOW_RESOURCE_MODE: bool = os.getenv("LOW_RESOURCE_MODE", "True").lower() == "true"

settings = Settings()