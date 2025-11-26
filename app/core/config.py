import os
from pydantic import BaseModel

class Settings(BaseModel):
    APP_NAME: str = "XTTS v2 Production Service"
    # Ortam değişkeninden oku, bulamazsan varsayılanı kullan
    MODEL_NAME: str = os.getenv("TTS_COQUI_SERVICE_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")
    DEVICE: str = "cuda" if os.getenv("CUDA_VISIBLE_DEVICES") else "cpu"
    # TOS Auto Accept
    COQUI_TOS_AGREED: str = "1"

settings = Settings()