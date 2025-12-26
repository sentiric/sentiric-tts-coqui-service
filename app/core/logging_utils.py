import logging
import sys
import json
from datetime import datetime

from pythonjsonlogger import jsonlogger
from rich.console import Console
from rich.logging import RichHandler
from app.core.config import settings

# Uvicorn loglarını yakalamak için
LOGGERS = ("uvicorn.asgi", "uvicorn.access", "uvicorn")

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # ISO 8601 Timestamp (UTC)
        if not log_record.get('timestamp'):
            now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            log_record['timestamp'] = now
            
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

        # Statik Servis Bilgisi (Log Aggregation için kritik)
        log_record['service'] = "tts-coqui-service"
        log_record['env'] = settings.ENV

def setup_logging():
    """
    Uygulama ve Uvicorn için merkezi loglama yapılandırması.
    Development: Rich (Renkli/Okunabilir)
    Production: JSON (Makine Okunabilir)
    """
    
    # Kök logger seviyesini belirle
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    # Mevcut handler'ları temizle (Çift loglamayı önle)
    logging.getLogger().handlers = []
    
    # --- STRATEJİ SEÇİMİ ---
    if settings.ENV == "development" or settings.DEBUG:
        # 🎨 DEVELOPMENT MODU: Rich Handler
        # Tarih formatı: Whisper servisindeki [YYYY-MM-DD HH:MM:SS.ms] formatına benzetildi.
        console = Console(width=160) # Geniş ekran desteği
        handler = RichHandler(
            console=console,
            show_time=True,
            show_level=True,
            show_path=False, # Dosya yolunu gizle (daha temiz)
            rich_tracebacks=True, # Renkli hata izleme
            tracebacks_show_locals=True, # Hata anındaki değişkenleri göster (Debug için harika)
            markup=True
        )
        handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%Y-%m-%d %H:%M:%S]"))
        
    else:
        # 🏭 PRODUCTION MODU: JSON Formatter
        handler = logging.StreamHandler(sys.stdout)
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s %(service)s %(trace_id)s'
        )
        handler.setFormatter(formatter)

    # --- YAPILANDIRMA ---
    
    # 1. Root Logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # 2. Uvicorn & Kütüphane Loglarını Ele Geçir
    for logger_name in LOGGERS:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [] # Uvicorn'un varsayılan handler'ını sil
        logging_logger.addHandler(handler) # Bizim handler'ı ekle
        logging_logger.propagate = False # Root'a tekrar gönderme (double log olmasın)

    # 3. Gürültücü kütüphaneleri sustur
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("numba").setLevel(logging.WARNING)

    # Test Logu
    logger = logging.getLogger("INIT")
    mode_icon = "🎨" if settings.ENV == "development" else "🏭"
    logger.info(f"{mode_icon} Logging initialized in {settings.ENV.upper()} mode.")