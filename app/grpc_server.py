import logging
import grpc
import time
from concurrent import futures
import asyncio

# Sentiric Contracts'tan üretilen kodlar
# Not: Eğer paket henüz yüklü değilse bu import hata verebilir.
# Production build pipeline'ında bu paketlerin varlığı garanti edilmelidir.
try:
    from sentiric.tts.v1 import tts_pb2
    from sentiric.tts.v1 import tts_pb2_grpc
except ImportError:
    # Fallback for build without contracts installed
    logging.warning("Sentiric Contracts not found. gRPC server will not start correctly.")
    tts_pb2 = None
    tts_pb2_grpc = None

from app.core.engine import tts_engine
from app.core.config import settings

logger = logging.getLogger("GRPC-SERVER")

class TextToSpeechServicer(tts_pb2_grpc.TextToSpeechServiceServicer if tts_pb2_grpc else object):
    """
    Sentiric TTS Contract'ını uygulayan gRPC servisi.
    Gateway katmanından gelen istekleri karşılar.
    """

    def Synthesize(self, request, context):
        if not tts_pb2:
            context.abort(grpc.StatusCode.UNIMPLEMENTED, "Contracts not loaded")

        start_time = time.perf_counter()
        try:
            # 1. Parametre Hazırlığı
            # Gateway'den gelen istekteki opsiyonel parametreleri engine formatına çevir
            params = {
                "text": request.text,
                "language": request.language_code,
                "speaker_idx": request.voice_selector or "Ana Florence", # Varsayılan
                # gRPC üzerinden gelen ham ses verisi (speaker_wav) desteği gerekirse eklenebilir
                # Şu anlık contract URL/path bazlı çalışıyor.
                "temperature": 0.75, # Standart değer
                "speed": 1.0,
                "output_format": "wav" # İç iletişimde genellikle WAV/PCM tercih edilir
            }

            # 2. Sentezleme (Global Lock ile Korunur)
            # tts_engine singleton olduğu için HTTP ile çakışma olmaz, lock sıraya koyar.
            audio_bytes = tts_engine.synthesize(params)

            # 3. Metrikler ve Loglama
            process_time = time.perf_counter() - start_time
            char_count = len(request.text)
            
            logger.info("grpc.request_handled", extra={
                "method": "Synthesize",
                "chars": char_count,
                "latency": f"{process_time:.3f}s"
            })

            # 4. Yanıt
            return tts_pb2.SynthesizeResponse(
                audio_content=audio_bytes,
                engine_used="coqui-xtts-v2"
            )

        except Exception as e:
            logger.error(f"gRPC Synthesize Error: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

async def serve_grpc():
    """Asenkron gRPC sunucusunu başlatır"""
    if not tts_pb2_grpc:
        logger.critical("❌ gRPC dependencies missing. Skipping gRPC server start.")
        return

    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=4))
    tts_pb2_grpc.add_TextToSpeechServiceServicer_to_server(TextToSpeechServicer(), server)
    
    listen_addr = f"[::]:{settings.GRPC_PORT}"
    server.add_insecure_port(listen_addr)
    
    logger.info(f"🚀 gRPC Server starting on {listen_addr}")
    await server.start()
    
    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        logger.info("🛑 gRPC Server stopping...")
        await server.stop(5)