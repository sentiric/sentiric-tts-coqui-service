import logging
import sys
import uvicorn.logging
from datetime import datetime
from pythonjsonlogger import jsonlogger
from app.core.config import settings

# Yakalanacak loglar
LOGGERS = ("uvicorn.asgi", "uvicorn.access", "uvicorn")

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Production için JSON Formatter (Governance Uyumlu)"""
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            log_record['timestamp'] = now
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
        log_record['service'] = "tts-coqui-service"
        log_record['env'] = settings.ENV

class RustStyleFormatter(logging.Formatter):
    """
    Development için Rust/Gateway loglarına benzeyen temiz formatter.
    Format: YYYY-MM-DDTHH:MM:SS.ssssssZ  LEVEL  logger: message
    """
    
    # ANSI Renk Kodları
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMAT = "%(asctime)sZ  %(levelname)-5s  %(name)s: %(message)s"

    FORMATS = {
        logging.DEBUG: grey + FORMAT + reset,
        logging.INFO: green + FORMAT + reset,
        logging.WARNING: yellow + FORMAT + reset,
        logging.ERROR: red + FORMAT + reset,
        logging.CRITICAL: bold_red + FORMAT + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        # ISO 8601 formatına benzer zaman damgası
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%dT%H:%M:%S.%f")
        return formatter.format(record)

def setup_logging():
    """
    Merkezi Loglama Yapılandırması.
    """
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.getLogger().handlers = []

    # Handler Seçimi
    handler = logging.StreamHandler(sys.stdout)

    if settings.ENV == "development":
        # 🎨 DEVELOPMENT: Rust Style Clean Text
        handler.setFormatter(RustStyleFormatter())
    else:
        # 🏭 PRODUCTION: JSON
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s %(service)s %(trace_id)s'
        )
        handler.setFormatter(formatter)

    # Root Logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Uvicorn Loglarını Ele Geçir
    for logger_name in LOGGERS:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = []
        logging_logger.addHandler(handler)
        logging_logger.propagate = False

    # Gürültü Engelleme
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("numba").setLevel(logging.WARNING)

    # Başlangıç Logu
    logger = logging.getLogger("INIT")
    mode = "DEVELOPMENT (Rust Style)" if settings.ENV == "development" else f"PRODUCTION (JSON) - ENV={settings.ENV}"
    logger.info(f"Log system initialized in {mode}")