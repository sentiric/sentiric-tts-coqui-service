# Dosya: app/grpc_server.py
import logging
import grpc
import os
from concurrent import futures
import asyncio

from sentiric.tts.v1 import coqui_pb2
from sentiric.tts.v1 import coqui_pb2_grpc

from app.core.engine import tts_engine
from app.core.config import settings

logger = logging.getLogger("GRPC-SERVER")

class TtsCoquiServicer(coqui_pb2_grpc.TtsCoquiServiceServicer):

    def CoquiSynthesize(self, request, context):
        logger.warning("Deprecated CoquiSynthesize RPC called. Client should migrate to streaming.", extra={"event": "DEPRECATED_RPC_CALL"})
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "Unary synthesis is deprecated, use streaming for low latency.")

    def CoquiSynthesizeStream(self, request, context):
        metadata = dict(context.invocation_metadata())
        trace_id = metadata.get('x-trace-id', 'unknown')
        span_id = metadata.get('x-span-id')
        tenant_id = metadata.get('x-tenant-id')
        
        log_extra = {
            'trace_id': trace_id,
            'span_id': span_id,
            'tenant_id': tenant_id
        }

        if not tenant_id or tenant_id == 'unknown':
            logger.error("Tenant ID is missing in gRPC metadata. Request rejected.", extra={**log_extra, 'event': 'MISSING_TENANT_ID'})
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "tenant_id is strictly required for isolation")
        
        logger.info(
            f"gRPC Stream Request | Text: '{request.text[:30]}...' | Lang: {request.language_code} | SampleRate: {request.sample_rate}",
            extra={**log_extra, 'event': 'GRPC_STREAM_REQUEST'}
        )
        
        try:
            params = {
                "text": request.text,
                "language": request.language_code,
                "speaker_idx": settings.DEFAULT_SPEAKER,
                "temperature": request.temperature or 0.75,
                "speed": request.speed or 1.0,
                "top_k": int(request.top_k) if request.top_k else 50,
                "top_p": request.top_p or 0.85,
                "repetition_penalty": request.repetition_penalty or 2.0,
                "output_format": "pcm",
                "speaker_wav": request.speaker_wav if request.speaker_wav else None,
                "sample_rate": int(request.sample_rate) if request.sample_rate > 0 else tts_engine.native_sample_rate
            }

            # [ARCH-COMPLIANCE FIX] context.is_active() ile iptal durumu Engine'e iletiliyor
            for chunk in tts_engine.synthesize_stream(params, is_aborted_cb=lambda: not context.is_active()):
                yield coqui_pb2.CoquiSynthesizeStreamResponse(audio_chunk=chunk, is_final=False)
            
            # Sadece client kopmadıysa Final flag gönder
            if context.is_active():
                yield coqui_pb2.CoquiSynthesizeStreamResponse(is_final=True)
                logger.info("gRPC Stream finished successfully.", extra={**log_extra, 'event': 'GRPC_STREAM_COMPLETE'})

        except Exception as e:
            logger.error(f"gRPC Stream Error: {e}", exc_info=True, extra={**log_extra, 'event': 'GRPC_STREAM_ERROR'})
            context.abort(grpc.StatusCode.INTERNAL, str(e))

def load_tls_credentials():
    try:
        with open(settings.TTS_COQUI_SERVICE_KEY_PATH, 'rb') as f: private_key = f.read()
        with open(settings.TTS_COQUI_SERVICE_CERT_PATH, 'rb') as f: certificate_chain = f.read()
        with open(settings.GRPC_TLS_CA_PATH, 'rb') as f: root_ca = f.read()
        server_credentials = grpc.ssl_server_credentials([(private_key, certificate_chain)], root_certificates=root_ca, require_client_auth=True)
        return server_credentials
    except Exception as e:
        logger.critical(f"Failed to load TLS certificates: {e}", extra={"event": "TLS_CERT_LOAD_ERROR"})
        raise e

async def serve_grpc():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=4))
    coqui_pb2_grpc.add_TtsCoquiServiceServicer_to_server(TtsCoquiServicer(), server)
    listen_addr = f"[::]:{settings.GRPC_PORT}"
    
    use_tls = all(p and os.path.exists(p) for p in[
        settings.TTS_COQUI_SERVICE_KEY_PATH, settings.TTS_COQUI_SERVICE_CERT_PATH, settings.GRPC_TLS_CA_PATH
    ])
    
    if not use_tls:
        logger.critical("ARCHITECTURE VIOLATION: TLS certificates are missing or invalid paths provided.", extra={"event": "TLS_CONFIG_MISSING"})
        raise RuntimeError("gRPC Server cannot start without valid mTLS certificates.")
        
    try:
        tls_creds = load_tls_credentials()
        server.add_secure_port(listen_addr, tls_creds)
        logger.info(f"gRPC Server (Coqui) starting on {listen_addr} (mTLS Enabled)", extra={"event": "GRPC_SERVER_READY"})
    except Exception as e:
        logger.error(f"Failed to initialize secure port, shutting down: {e}", extra={"event": "GRPC_SERVER_INIT_FAIL"})
        raise e

    await server.start()
    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        logger.info("gRPC Server stopping...", extra={"event": "GRPC_SERVER_STOPPING"})
        await server.stop(5)