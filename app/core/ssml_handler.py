import re
import logging
from typing import List, Dict, Any
# Standart kütüphane yerine güvenli parser kullanıyoruz
from defusedxml import ElementTree as ET 

logger = logging.getLogger("SSML-HANDLER")

class SSMLHandler:
    """
    Görevi: SSML (Speech Synthesis Markup Language) metinlerini GÜVENLİ BİR ŞEKİLDE parse etmek
    ve inferans motorunun anlayacağı segmentlere bölmek.
    """

    @staticmethod
    def is_ssml(text: str) -> bool:
        return "<speak>" in text

    @staticmethod
    def parse(ssml_text: str, default_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            # XML güvenlik önlemi: Ampersand kaçışı
            ssml_text = ssml_text.replace("&", "&amp;") 
            
            # Root wrapper ekle (Parser hatasını önlemek için)
            # defusedxml string parse ederken fromstring kullanır
            if not ssml_text.strip().startswith("<root>"):
                root_text = f"<root>{ssml_text}</root>"
            else:
                root_text = ssml_text

            # GÜVENLİ PARSE İŞLEMİ (Billion Laughs korumalı)
            root = ET.fromstring(root_text)
            segments = []
            
            def process_element(element, current_params):
                # 1. Elementin kendi metni (Head Text)
                if element.text and element.text.strip():
                    segments.append({
                        'type': 'text', 
                        'content': element.text.strip(), 
                        'params': current_params.copy()
                    })
                
                # 2. Alt elementler (Çocuklar)
                for child in element:
                    child_params = current_params.copy()
                    
                    if child.tag == 'break':
                        duration = 0.5
                        try: 
                            val = child.get('time', '0.5s').lower().replace('s', '').replace('ms', '')
                            # Basit dönüşüm: ms ise /1000, s ise direkt float
                            if 'ms' in child.get('time', ''):
                                duration = float(val) / 1000.0
                            else:
                                duration = float(val)
                        except: 
                            pass
                        segments.append({'type': 'break', 'duration': duration})
                    
                    elif child.tag == 'prosody':
                        rate = child.get('rate')
                        mapping = {"x-slow": 0.7, "slow": 0.85, "medium": 1.0, "fast": 1.2, "x-fast": 1.4}
                        if rate in mapping: 
                            child_params['speed'] = mapping[rate]
                        else: 
                            try: 
                                child_params['speed'] = float(rate)
                            except: 
                                pass
                                
                    elif child.tag == 'emphasis':
                        level = child.get('level', 'moderate')
                        if level in ["strong", "moderate"]:
                            # Vurgu için hızı biraz düşür, tekrar cezasını artır (daha net artikülasyon)
                            child_params['speed'] = child_params.get('speed', 1.0) * 0.9
                            child_params['repetition_penalty'] = child_params.get('repetition_penalty', 2.0) * 1.2
                    
                    # Rekürsif işleme
                    process_element(child, child_params)
                    
                    # 3. Elementin kapanışından sonraki metin (Tail Text)
                    if child.tail and child.tail.strip():
                        segments.append({
                            'type': 'text', 
                            'content': child.tail.strip(), 
                            'params': current_params.copy()
                        })

            process_element(root, default_params)
            
            # Fallback: Parse sonucu boşsa ham metni döndür (Ama tagleri temizle)
            if not segments: 
                clean_text = "".join(root.itertext())
                return [{'type': 'text', 'content': clean_text, 'params': default_params}]
                
            return segments

        except Exception as e:
            logger.warning(f"SSML Parse Error: {e}. Falling back to plain text regex clean.")
            # Regex ile tagleri temizle ve düz metin döndür
            clean_text = re.sub(r'<[^>]+>', '', ssml_text)
            return [{'type': 'text', 'content': clean_text, 'params': default_params}]

ssml_handler = SSMLHandler()