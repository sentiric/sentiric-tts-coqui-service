import logging
import sys
from pythonjsonlogger import jsonlogger
from app.core.config import settings

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            # Governance Standardı: ISO 8601 Time Format
            log_record['timestamp'] = record.asctime
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

        # Statik Servis Bilgisi
        log_record['service'] = "tts-coqui-service"

def setup_logging():
    logger = logging.getLogger()
    
    # Mevcut handlerları temizle (Uvicorn'un defaultlarını ezmek için)
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
        # timestamp, level, name, message zorunlu alanlar
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Log Seviyesi
    logger.setLevel(logging.INFO)
    
    # Harici kütüphanelerin gürültüsünü azalt
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)