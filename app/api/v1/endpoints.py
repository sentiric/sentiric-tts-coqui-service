# app/api/v1/endpoints.py
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, HttpUrl
from typing import Optional

from app.services.tts_service import tts_engine
from app.core.logging import logger

router = APIRouter()

class SynthesizeRequest(BaseModel):
    text: str
    language: str = "tr"
    speaker_wav_url: Optional[HttpUrl] = None

@router.post("/synthesize", response_class=Response)
async def synthesize(request: SynthesizeRequest):
    if not tts_engine.is_ready():
        raise HTTPException(status_code=503, detail="TTS motoru şu an kullanılamıyor.")

    try:
        # Pydantic v2'de HttpUrl nesnesini string'e çevirmek için str() kullanmak en iyisidir.
        speaker_wav_str = str(request.speaker_wav_url) if request.speaker_wav_url else None
        
        wav_bytes = await tts_engine.synthesize(
            request.text, 
            request.language, 
            speaker_wav_str
        )
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as e:
        logger.error("Sentezleme sırasında beklenmedik bir hata oluştu.", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ses üretimi sırasında bir hata oluştu: {e}")