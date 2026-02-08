import logging
import sys
import uvicorn.logging
from datetime import datetime
from pythonjsonlogger import jsonlogger
from app.core.config import settings

# [LOGLAMA GÜNCELLEMESİ]: /health dışındaki tüm access logları artık JSON olarak basılacak.
LOGGERS_TO_CAPTURE = ("uvicorn.asgi", "uvicorn.access", "uvicorn")

class HealthEndpointFilter(logging.Filter):
    """Sadece /health ve /healthz endpoint'lerini loglardan temizler."""
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        is_health_check = "GET /health" in message or "GET /healthz" in message
        # Sadece 200 OK olan sağlık kontrollerini gizle, hatalı olanlar görünsün.
        return not (is_health_check and ' 200 ' in message)

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Platform standardı ile uyumlu JSON log formatı."""
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        log_record['level'] = record.levelname
        log_record['service'] = "tts-coqui-service"

        # uvicorn.access loglarından HTTP detaylarını al
        if record.name == "uvicorn.access":
            log_record['http.method'] = record.args[1]
            log_record['http.path'] = record.args[2]
            log_record['http.status_code'] = record.args[4]
            log_record['http.client_addr'] = record.args[0]
            # Mesajı temizle, bilgiler zaten alanlarda var.
            log_record['message'] = f"{record.args[1]} {record.args[2]} - {record.args[4]}"
        
        # trace_id'yi log'a ekle (middleware'den gelir)
        if hasattr(record, 'trace_id'):
            log_record['trace_id'] = record.trace_id

def setup_logging():
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.getLogger().handlers = []
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(service)s %(name)s %(message)s %(trace_id)s'
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    for logger_name in LOGGERS_TO_CAPTURE:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [handler]
        logging_logger.propagate = False

    # Sadece başarılı sağlık kontrollerini gizle
    logging.getLogger("uvicorn.access").addFilter(HealthEndpointFilter())
    
    logging.getLogger("numba").setLevel(logging.WARNING)
    logger = logging.getLogger("INIT")
    logger.info(f"Log system initialized in PRODUCTION (JSON) mode.")```
