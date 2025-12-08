import logging
import grpc
import time
from concurrent import futures
import asyncio

# Sentiric Contracts (v1.12.0 Güncellemesi)
try:
    # DÜZELTME: tts_pb2 yerine coqui_pb2
    from sentiric.tts.v1 import coqui_pb2
    from sentiric.tts.v1 import coqui_pb2_grpc
except ImportError:
    logging.warning("Sentiric Contracts not found. gRPC server will not start correctly.")
    coqui_pb2 = None
    coqui_pb2_grpc = None

from app.core.engine import tts_engine
from app.core.config import settings

logger = logging.getLogger("GRPC-SERVER")

# DÜZELTME: Sınıf adı ve miras alınan sınıf değişti
class TtsCoquiServicer(coqui_pb2_grpc.TtsCoquiServiceServicer if coqui_pb2_grpc else object):
    """
    Sentiric TTS (Coqui Engine) Contract'ını uygulayan gRPC servisi.
    Gateway katmanından gelen motor-spesifik istekleri karşılar.
    """

    # DÜZELTME: Metod adı CoquiSynthesize (Unary)
    def CoquiSynthesize(self, request, context):
        if not coqui_pb2:
            context.abort(grpc.StatusCode.UNIMPLEMENTED, "Contracts not loaded")

        start_time = time.perf_counter()
        try:
            # 1. Parametre Hazırlığı
            # Proto mesajından Engine parametrelerine dönüşüm
            params = {
                "text": request.text,
                "language": request.language_code,
                # Coqui motoru 'speaker_idx' bekler. 
                # Gateway buraya wav dosyası bytes göndermiş olabilir (Cloning için) 
                # veya biz varsayılan speaker'ı kullanırız.
                # Şimdilik basitlik adına varsayılanı veya config'i kullanıyoruz.
                # Gerçek cloning implementasyonunda 'request.speaker_wav' işlenmeli.
                "speaker_idx": settings.DEFAULT_SPEAKER, 
                "temperature": request.temperature or 0.75,
                "speed": request.speed or 1.0,
                "top_k": int(request.top_k) if request.top_k else 50,
                "top_p": request.top_p or 0.85,
                "repetition_penalty": request.repetition_penalty or 5.0,
                "output_format": request.output_format or "wav"
            }

            # 2. Sentezleme (Global Lock ile Korunur)
            audio_bytes = tts_engine.synthesize(params)

            # 3. Metrikler ve Loglama
            process_time = time.perf_counter() - start_time
            char_count = len(request.text)
            
            logger.info("grpc.request_handled", extra={
                "method": "CoquiSynthesize",
                "chars": char_count,
                "latency": f"{process_time:.3f}s"
            })

            # 4. Yanıt
            # DÜZELTME: CoquiSynthesizeResponse
            return coqui_pb2.CoquiSynthesizeResponse(
                audio_content=audio_bytes
                # is_final stream olmadığı için burada yok veya true kabul edilir
            )

        except Exception as e:
            logger.error(f"gRPC Synthesize Error: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    # DÜZELTME: Stream Metodu Eklendi (Eğer contract'ta varsa implemente edilmeli)
    # Şimdilik Unary mantığıyla stream simülasyonu veya boş bırakılabilir.
    # Ancak contract'ta tanımlı olduğu için boş da olsa override etmek iyidir.
    def CoquiSynthesizeStream(self, request, context):
        # Basit implementasyon: Tek parça gönder
        response = self.CoquiSynthesize(request, context)
        yield coqui_pb2.CoquiSynthesizeStreamResponse(
            audio_chunk=response.audio_content,
            is_final=True
        )

async def serve_grpc():
    """Asenkron gRPC sunucusunu başlatır"""
    if not coqui_pb2_grpc:
        logger.critical("❌ gRPC dependencies missing. Skipping gRPC server start.")
        return

    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=4))
    
    # DÜZELTME: Servis ekleme metodu değişti
    coqui_pb2_grpc.add_TtsCoquiServiceServicer_to_server(TtsCoquiServicer(), server)
    
    listen_addr = f"[::]:{settings.GRPC_PORT}"
    server.add_insecure_port(listen_addr)
    
    logger.info(f"🚀 gRPC Server (Coqui Engine) starting on {listen_addr}")
    await server.start()
    
    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        logger.info("🛑 gRPC Server stopping...")
        await server.stop(5)