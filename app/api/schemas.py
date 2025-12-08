from pydantic import BaseModel, Field
from typing import Optional
from app.core.config import settings

# SSML açıklama metni
ssml_description = """
Metin girişi hem düz metin hem de SSML (Speech Synthesis Markup Language) formatını destekler.
SSML kullanmak için metninizi `<speak>` etiketleri arasına alın.

**Desteklenen Etiketler:**
1.  `<break time="[saniye]s" />`
2.  `<prosody rate="[hız]">...</prosody>`
3.  `<emphasis level="[seviye]">...</emphasis>`
"""

class TTSRequest(BaseModel):
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=5000,
        description=ssml_description
    )
    language: str = Field(
        settings.DEFAULT_LANGUAGE, 
        pattern="^(en|es|fr|de|it|pt|pl|tr|ru|nl|cs|ar|zh-cn|ja|hu|ko)$"
    )
    speaker_idx: Optional[str] = settings.DEFAULT_SPEAKER
    
    # Tuning Parametreleri - Defaults from Config
    temperature: float = Field(settings.DEFAULT_TEMPERATURE, ge=0.01, le=2.0)
    speed: float = Field(settings.DEFAULT_SPEED, ge=0.25, le=4.0)
    top_k: int = Field(settings.DEFAULT_TOP_K, ge=1)
    top_p: float = Field(settings.DEFAULT_TOP_P, ge=0.01, le=1.0)
    repetition_penalty: float = Field(settings.DEFAULT_REPETITION_PENALTY, ge=1.0)
    
    # Sistem Parametreleri
    stream: bool = Field(settings.ENABLE_STREAMING, description="Chunked transfer encoding kullanır")
    output_format: str = Field(settings.DEFAULT_OUTPUT_FORMAT, pattern="^(wav|mp3|opus|pcm)$")
    sample_rate: int = Field(settings.DEFAULT_SAMPLE_RATE)
    # YENİ PARAMETRE: Akış davranışını kontrol eder.
    split_sentences: bool = Field(True, description="Düşük gecikme için metni cümlelere böl. Uzun metinlerde takılma olursa 'false' deneyin.")

class OpenAISpeechRequest(BaseModel):
    """OpenAI API uyumluluğu için şema"""
    model: str = Field("tts-1", description="Yoksayılır")
    input: str = Field(..., description="Okunacak metin")
    voice: str = Field("alloy", description="Ses ID'si (Map edilir)")
    response_format: str = Field("mp3", description="mp3, opus, aac, flac, wav, pcm")
    speed: float = Field(1.0, description="0.25 - 4.0")