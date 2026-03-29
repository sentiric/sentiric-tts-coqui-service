# Dosya: app/core/middleware.py
import time
import uuid
import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging_utils import trace_id_var, span_id_var, tenant_id_var

logger = logging.getLogger("MIDDLEWARE")

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        # 1. Başlıkları Okuma
        trace_id = request.headers.get("x-trace-id") or request.headers.get("x-request-id") or str(uuid.uuid4())
        span_id = request.headers.get("x-span-id")
        tenant_id = request.headers.get("x-tenant-id")

        # Context Variables atama (Logger tarafından kullanılacak)
        token_t = trace_id_var.set(trace_id)
        token_s = span_id_var.set(span_id)
        token_ten = tenant_id_var.set(tenant_id)

        # [FIX] Statik dosyaların bloklanmaması için mantık tersine çevrildi
        # Yalnızca /api/ veya /v1/ ile başlayan (iş mantığı) rotalar korunur.
        is_api_route = request.url.path.startswith("/api/") or request.url.path.startswith("/v1/")
        is_public_endpoint = not is_api_route or request.url.path.startswith("/api/config")

        # [ARCH-COMPLIANCE] Strict Tenant Isolation Check
        if not is_public_endpoint:
            if not tenant_id or tenant_id == "unknown":
                logger.error("Tenant ID is missing in HTTP headers. Request rejected.", extra={"event": "MISSING_TENANT_ID"})
                trace_id_var.reset(token_t)
                span_id_var.reset(token_s)
                tenant_id_var.reset(token_ten)
                return JSONResponse(
                    status_code=400,
                    content={"error": "tenant_id header is strictly required for isolation", "type": "invalid_request_error"}
                )

        # 2. Standalone Security Check (API Key)
        if settings.API_KEY and not is_public_endpoint:
            client_key = request.headers.get("X-API-Key")
            if client_key != settings.API_KEY:
                logger.warning(f"Unauthorized access attempt from {request.client.host}", extra={"event": "UNAUTHORIZED_ACCESS"})
                trace_id_var.reset(token_t)
                span_id_var.reset(token_s)
                tenant_id_var.reset(token_ten)
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API Key. This is a secured standalone instance."}
                )

        # 3. Process Request
        try:
            response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id
            return response
        except Exception as e:
            logger.error(f"Unhandled Exception: {e}", exc_info=True, extra={"event": "HTTP_UNHANDLED_EXCEPTION"})
            raise e
        finally:
            # Context temizliği
            trace_id_var.reset(token_t)
            span_id_var.reset(token_s)
            tenant_id_var.reset(token_ten)