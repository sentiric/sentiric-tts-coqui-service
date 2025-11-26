import logging
import sys
from datetime import datetime
from pythonjsonlogger import jsonlogger
from app.core.config import settings

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # FIX: record.asctime her zaman mevcut değildir.
        # ISO 8601 formatında timestamp ekliyoruz.
        if not log_record.get('timestamp'):
            now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            log_record['timestamp'] = now
            
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

        # Statik Servis Bilgisi
        log_record['service'] = "tts-coqui-service"

def setup_logging():
    logger = logging.getLogger()
    
    # Mevcut handlerları temizle
    if logger.handlers:
        logger.handlers = []

    handler = logging.StreamHandler(sys.stdout)

    if settings.DEBUG:
        # Geliştirme Ortamı: Renkli ve Okunabilir
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        # Üretim Ortamı: JSON (Governance Standardı: OBS-2.1)
        # timestamp alanını add_fields içinde eklediğimiz için burada formata koymuyoruz
        formatter = CustomJsonFormatter(
            '%(level)s %(name)s %(message)s'
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    logger.setLevel(logging.INFO)
    
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)