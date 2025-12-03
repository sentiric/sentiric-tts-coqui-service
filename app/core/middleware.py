import time
import uuid
import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings

logger = logging.getLogger("MIDDLEWARE")

class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    1. Trace ID Yönetimi: Gelen istekte varsa kullanır, yoksa oluşturur.
    2. API Key Güvenliği: Eğer konfigüre edildiyse API anahtarını doğrular.
    3. Performans Loglama: İşlem süresini ölçer.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        # 1. Trace ID (Governance Standardı: OBS-2.1)
        # Gateway'den gelen 'x-trace-id' veya 'x-request-id' başlıklarını kontrol et
        trace_id = request.headers.get("x-trace-id") or request.headers.get("x-request-id") or str(uuid.uuid4())
        
        # Log Context'e ekle (structlog/jsonlogger tarafından kullanılacak)
        # Not: Asenkron context yönetimi kütüphane bağımlı olduğu için burada basitçe
        # response header'a ekleyerek taşıyoruz.
        
        # 2. Standalone Security Check
        if settings.API_KEY:
            # Sağlık kontrolleri ve statik dosyalar hariç
            if not (request.url.path.startswith("/health") or 
                    request.url.path.startswith("/static") or 
                    request.url.path == "/" or
                    request.url.path == "/favicon.ico"):
                
                client_key = request.headers.get("X-API-Key")
                if client_key != settings.API_KEY:
                    logger.warning(f"Unauthorized access attempt from {request.client.host}")
                    return await self._auth_error()

        # 3. Process Request
        try:
            response = await call_next(request)
            
            # Trace ID'yi yanıta ekle (Zincir takibi için)
            response.headers["X-Trace-ID"] = trace_id
            
            process_time = (time.perf_counter() - start_time) * 1000
            
            # Access Log (JSON formatına uygun olması için logging_utils halledecek, burada manuel print yapmıyoruz)
            return response
            
        except Exception as e:
            logger.error(f"Unhandled Exception: {e} | Trace: {trace_id}")
            raise e

    async def _auth_error(self):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API Key. This is a secured standalone instance."}
        )