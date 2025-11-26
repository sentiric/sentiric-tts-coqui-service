import re
import logging

logger = logging.getLogger("TEXT-NORM")

class TextNormalizer:
    @staticmethod
    def normalize(text: str, lang: str = "tr") -> str:
        if not text: return ""
        
        original_text = text
        
        # 1. Genel Temizlik (Tüm diller)
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace("’", "'").replace("“", '"').replace("”", '"')
        
        # 2. Türkçe Özel Kurallar
        if lang == "tr":
            # Tarih: 26.11.2025 -> 26 kasım 2025
            # (Basit bir regex, geliştirilebilir)
            
            # Birimler
            text = text.replace("km/h", " kilometre bölü saat ")
            text = text.replace("kg ", " kilogram ")
            text = text.replace("cm ", " santimetre ")
            text = text.replace("mm ", " milimetre ")
            
            # Sayı sonu nokta (Sıra sayısı karışıklığı için)
            # "2025." -> "2025" (Eğer cümle sonu değilse)
            # Bu regex: Sayı + Nokta + Boşluk -> Sayı + Boşluk
            text = re.sub(r'(\d+)\.\s', r'\1 ', text)
            
            # İngilizce terimler (Okunuş düzeltme - Opsiyonel)
            text = text.replace("CPU", "si pi yu")
            text = text.replace("GPU", "ci pi yu")
            text = text.replace("AI", "ey ay")

        # 3. XML/SSML Temizliği (Engine içinde parse ediliyor ama burada ön temizlik yapılabilir)
        # Şimdilik SSML'e dokunmuyoruz, engine hallediyor.

        if text != original_text:
            logger.debug(f"Normalized: '{original_text[:20]}...' -> '{text[:20]}...'")
            
        return text

normalizer = TextNormalizer()