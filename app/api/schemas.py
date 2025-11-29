from pydantic import BaseModel, Field
from typing import Optional

# SSML için detaylı açıklama metni
ssml_description = """
Metin girişi hem düz metin hem de SSML (Speech Synthesis Markup Language) formatını destekler.
SSML kullanmak için metninizi `<speak>` etiketleri arasına alın.

**Desteklenen Etiketler:**

1.  **`<break time="[saniye]s" />`**: Belirtilen süre kadar duraklama ekler.
    *   Örnek: `<break time="1.5s" />`

2.  **`<prosody rate="[hız]">...</prosody>`**: İçindeki metnin konuşma hızını ayarlar.
    *   `rate` Değerleri: `x-slow`, `slow`, `medium`, `fast`, `x-fast` veya `0.5` ile `2.0` arası bir sayı.
    *   Örnek: `<prosody rate="slow">Bu metin yavaş okunacak.</prosody>`

3.  **`<emphasis level="[seviye]">...</emphasis>`**: İçindeki metni vurgular.
    *   `level` Değerleri: `strong`, `moderate` (varsayılan), `reduced`.
    *   Örnek: `<emphasis level="strong">Bu kelime vurgulu.</emphasis>`

**Komple Örnek:**
```xml
<speak>
  Bu normal hızda. <break time="1s"/>
  <prosody rate="fast">Bu bölüm ise çok daha hızlı olacak.</prosody>
  Unutmamanız gereken en <emphasis level="strong">önemli</emphasis> şey budur.
</speak>
```
"""

class TTSRequest(BaseModel):
    text: str = Field(
        ..., 
        min_length=2, 
        max_length=5000,
        description=ssml_description
    )
    language: str = Field("tr", pattern="^(en|es|fr|de|it|pt|pl|tr|ru|nl|cs|ar|zh|ja|hu|ko)$")
    speaker_idx: Optional[str] = "Ana Florence"
    
    # Tuning
    temperature: float = 0.75
    speed: float = 1.0
    top_k: int = 50
    top_p: float = 0.85
    repetition_penalty: float = 2.0
    
    # Pro Features
    stream: bool = Field(False, description="Eğer True ise, ses parça parça (chunk) gelir.")
    # FIX: Regex genişletildi (wav, mp3, opus, pcm)
    output_format: str = Field("wav", pattern="^(wav|mp3|opus|pcm)$", description="Ses dosya formatı")
    split_sentences: bool = Field(True, description="Uzun metinleri cümlelere böl (Daha doğal duraklama)")


class OpenAISpeechRequest(BaseModel):
    model: str = Field("tts-1", description="Model adı (Göz ardı edilir, backend varsayılanı kullanır)")
    input: str = Field(..., description="Okunacak metin")
    voice: str = Field("alloy", description="Ses ID'si")
    response_format: str = Field("mp3", description="Çıktı formatı (mp3, opus, aac, flac, wav, pcm)")
    speed: float = Field(1.0, description="Konuşma hızı (0.25 - 4.0)")