import logging
import sys
import os
import contextvars
from datetime import datetime
from typing import Optional
from pythonjsonlogger import jsonlogger
from app.core.config import settings

# [ARCH-COMPLIANCE] Asenkron Context Propagation
trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id", default=None
)
span_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "span_id", default=None
)
tenant_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "tenant_id", default=None
)

LOGGERS_TO_CAPTURE = ("uvicorn.asgi", "uvicorn.access", "uvicorn")


class HealthEndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        is_health_check = "GET /health" in message or "GET /healthz" in message
        return not (is_health_check and " 200 " in message)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)

        for key in list(log_record.keys()):
            if key != "message":
                del log_record[key]

        log_record["schema_v"] = "1.0.0"
        log_record["ts"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        severity = record.levelname.upper()
        if severity == "WARNING":
            severity = "WARN"
        if severity == "CRITICAL":
            severity = "FATAL"
        log_record["severity"] = severity

        t_id = getattr(record, "trace_id", trace_id_var.get())
        s_id = getattr(record, "span_id", span_id_var.get())
        ten_id = getattr(record, "tenant_id", tenant_id_var.get())

        log_record["tenant_id"] = ten_id if ten_id else None
        log_record["resource"] = {
            "service.name": "tts-coqui-service",
            "service.version": settings.APP_VERSION,
            "service.env": settings.ENV,
            "host.name": os.getenv("HOSTNAME", "unknown"),
        }
        log_record["trace_id"] = t_id if t_id else None
        log_record["span_id"] = s_id if s_id else None
        log_record["event"] = getattr(record, "event", "LOG_EVENT")
        log_record["message"] = record.getMessage()

        if record.name == "uvicorn.access":
            log_record["event"] = "HTTP_ACCESS"
            log_record["attributes"] = {
                "http.method": record.args[1] if len(record.args) > 1 else None,
                "http.path": record.args[2] if len(record.args) > 2 else None,
                "http.status_code": record.args[4] if len(record.args) > 4 else None,
                "http.client_addr": record.args[0] if len(record.args) > 0 else None,
            }


def setup_logging():
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.getLogger().handlers = []
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    for logger_name in LOGGERS_TO_CAPTURE:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [handler]
        logging_logger.propagate = False
    logging.getLogger("uvicorn.access").addFilter(HealthEndpointFilter())
    logging.getLogger("numba").setLevel(logging.WARNING)
    logger = logging.getLogger("INIT")
    logger.info(
        "Log system initialized in PRODUCTION (SUTS v4.0 JSON) mode.",
        extra={"event": "LOGGER_INIT"},
    )
