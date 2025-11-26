import re
import logging

logger = logging.getLogger("TEXT-NORM")

class TextNormalizer:
    """
    Görevi: Ham metni modele girmeden önce temizlemek ve standartlaştırmak.
    """
    
    @staticmethod
    def normalize(text: str, lang: str = "tr") -> str:
        if not text: 
            return ""
        
        original_text = text
        
        # 1. Genel Temizlik
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace("’", "'").replace("“", '"').replace("”", '"')
        
        # 2. Dile Özel Kurallar (Genişletilebilir)
        if lang == "tr":
            # Birim düzeltmeleri
            text = text.replace("km/h", " kilometre bölü saat ")
            text = text.replace("kg", " kilogram ")
            text = text.replace("cm", " santimetre ")
            text = text.replace("mm", " milimetre ")
            
            # Sayı sonu nokta düzeltmesi (Sıra sayısı karışıklığını önler)
            # Örn: "2025. yılında" -> "2025 yılında" (Noktayı kaldırır)
            text = re.sub(r'(\d+)\.\s', r'\1 ', text)

        return text

normalizer = TextNormalizer()