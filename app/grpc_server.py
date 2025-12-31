import logging
import grpc
import time
import os
from concurrent import futures
import asyncio

try:
    from sentiric.tts.v1 import coqui_pb2
    from sentiric.tts.v1 import coqui_pb2_grpc
except ImportError:
    logging.warning("Sentiric Contracts not found. gRPC server will not start correctly.")
    coqui_pb2 = None
    coqui_pb2_grpc = None

from app.core.engine import tts_engine
from app.core.config import settings

logger = logging.getLogger("GRPC-SERVER")

class TtsCoquiServicer(coqui_pb2_grpc.TtsCoquiServiceServicer if coqui_pb2_grpc else object):

    def CoquiSynthesize(self, request, context):
        if not coqui_pb2:
            context.abort(grpc.StatusCode.UNIMPLEMENTED, "Contracts not loaded")

        start_time = time.perf_counter()
        try:
            params = {
                "text": request.text,
                "language": request.language_code,
                "speaker_idx": settings.DEFAULT_SPEAKER, 
                "temperature": request.temperature or 0.75,
                "speed": request.speed or 1.0,
                "top_k": int(request.top_k) if request.top_k else 50,
                "top_p": request.top_p or 0.85,
                "repetition_penalty": request.repetition_penalty or 5.0,
                "output_format": request.output_format or "wav"
            }

            audio_bytes = tts_engine.synthesize(params)

            process_time = time.perf_counter() - start_time
            char_count = len(request.text)
            
            logger.info("grpc.request_handled", extra={
                "method": "CoquiSynthesize",
                "chars": char_count,
                "latency": f"{process_time:.3f}s"
            })

            return coqui_pb2.CoquiSynthesizeResponse(
                audio_content=audio_bytes
            )

        except Exception as e:
            logger.error(f"gRPC Synthesize Error: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def CoquiSynthesizeStream(self, request, context):
        if not coqui_pb2:
            context.abort(grpc.StatusCode.UNIMPLEMENTED, "Contracts not loaded")

        response = self.CoquiSynthesize(request, context)
        yield coqui_pb2.CoquiSynthesizeStreamResponse(
            audio_chunk=response.audio_content,
            is_final=True
        )

def load_tls_credentials():
    try:
        with open(settings.TTS_COQUI_SERVICE_KEY_PATH, 'rb') as f:
            private_key = f.read()
        with open(settings.TTS_COQUI_SERVICE_CERT_PATH, 'rb') as f:
            certificate_chain = f.read()
        with open(settings.GRPC_TLS_CA_PATH, 'rb') as f:
            root_ca = f.read()

        server_credentials = grpc.ssl_server_credentials(
            [(private_key, certificate_chain)],
            root_certificates=root_ca,
            require_client_auth=True
        )
        return server_credentials
    except Exception as e:
        logger.critical(f"🔥 Failed to load TLS certificates: {e}")
        raise e

async def serve_grpc():
    if not coqui_pb2_grpc:
        logger.critical("❌ gRPC dependencies missing. Skipping gRPC server start.")
        return

    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=4))
    coqui_pb2_grpc.add_TtsCoquiServiceServicer_to_server(TtsCoquiServicer(), server)
    
    listen_addr = f"[::]:{settings.GRPC_PORT}"
    
    # [FIX] Insecure Fallback Logic
    # Sertifika yolları boşsa veya yoksa Insecure başlat
    use_tls = (
        settings.TTS_COQUI_SERVICE_KEY_PATH and os.path.exists(settings.TTS_COQUI_SERVICE_KEY_PATH) and
        settings.TTS_COQUI_SERVICE_CERT_PATH and os.path.exists(settings.TTS_COQUI_SERVICE_CERT_PATH) and
        settings.GRPC_TLS_CA_PATH and os.path.exists(settings.GRPC_TLS_CA_PATH)
    )

    if use_tls:
        try:
            tls_creds = load_tls_credentials()
            server.add_secure_port(listen_addr, tls_creds)
            logger.info(f"🔒 gRPC Server (Coqui) starting on {listen_addr} (mTLS Enabled)")
        except Exception:
            logger.error("Failed to initialize secure port, shutting down.")
            return
    else:
        # INSECURE MODE
        logger.warning(f"⚠️ TLS paths missing or invalid. Starting gRPC Server (Coqui) on {listen_addr} (INSECURE)")
        server.add_insecure_port(listen_addr)

    await server.start()
    
    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        logger.info("🛑 gRPC Server stopping...")
        await server.stop(5)