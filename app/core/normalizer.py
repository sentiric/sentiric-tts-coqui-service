import re
import logging

logger = logging.getLogger("TEXT-NORM")

class TextNormalizer:
    @staticmethod
    def normalize(text: str, lang: str = "tr") -> str:
        if not text:
            return ""

        original_text = text

        # ----------------------------------------------------
        # 1. TEMEL TEMİZLİK
        # ----------------------------------------------------
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace("’", "'").replace("“", '"').replace("”", '"')

        # ----------------------------------------------------
        # 2. TARİH DÖNÜŞTÜRME (26.11.2025 → “26 kasım 2025”)
        # ----------------------------------------------------
        def convert_date(match):
            day, month, year = match.groups()
            months = {
                "01": "ocak", "1": "ocak",
                "02": "şubat", "2": "şubat",
                "03": "mart", "3": "mart",
                "04": "nisan", "4": "nisan",
                "05": "mayıs", "5": "mayıs",
                "06": "haziran", "6": "haziran",
                "07": "temmuz", "7": "temmuz",
                "08": "ağustos", "8": "ağustos",
                "09": "eylül", "9": "eylül",
                "10": "ekim",
                "11": "kasım",
                "12": "aralık"
            }
            return f"{int(day)} {months[month]} {year}"

        text = re.sub(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b', convert_date, text)

        # ----------------------------------------------------
        # 3. BİRİMLERİ DOĞAL TÜRKÇEYE DÖNÜŞTÜRME
        # ----------------------------------------------------
        unit_map = {
            r'(\d+)\s*km/h': r'\1 kilometre saat hızla',
            r'(\d+)\s*kg\b': r'\1 kilogram',
            r'(\d+)\s*cm\b': r'\1 santimetre',
            r'(\d+)\s*mm\b': r'\1 milimetre',
        }

        for pattern, repl in unit_map.items():
            text = re.sub(pattern, repl, text)

        # ----------------------------------------------------
        # 4. SAYI + NOKTA SORUNUNU DÜZELTME
        # (“2025.” cümle sonu ile “2025. sırada” ayrımı)
        # ----------------------------------------------------
        text = re.sub(r'(\d+)\.(?=\s+[a-zA-ZŞşÇçĞğİıÖöÜü])', r'\1', text)

        # ----------------------------------------------------
        # 5. İNGİLİZCE KISALTMA OKUMALARI
        # Fonetik yerine HARF HARF okuma (en doğal çözüm)
        # ----------------------------------------------------
        spellout = {
            "HTML": "eyç ti em el",
            "CPU": "ci pi yu",
            "GPU": "gi pi u",
            "API": "ey pi a",
            "AI": "ey ay",
            "NASA": "NA SA",  # (Bu ayarlanabilir)
        }

        for key, val in spellout.items():
            text = re.sub(rf"\b{key}\b", val, text)

        # ----------------------------------------------------
        # 6. NOKTALAMA: İnsan konuşmasına uygun hale getir
        # ----------------------------------------------------
        text = text.replace("...", " … ")   # doğal duraklama
        text = text.replace("–", " - ")
        text = text.replace("—", " - ")

        # ----------------------------------------------------
        # Debug Log
        # ----------------------------------------------------
        if text != original_text:
            logger.debug(f"Normalized: '{original_text[:30]}...' -> '{text[:30]}...'")

        return text

normalizer = TextNormalizer()
