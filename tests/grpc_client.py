import os
import grpc
import logging
import time

# Sentiric Contracts (Otomatik üretilen kodlar)
# DÜZELTME: Importlar
from sentiric.tts.v1 import coqui_pb2
from sentiric.tts.v1 import coqui_pb2_grpc

# Loglama Ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("TEST-CLIENT")

def run_test():
    TARGET_HOST = os.getenv("TTS_SERVICE_HOST", "localhost")
    TARGET_PORT = os.getenv("TTS_SERVICE_PORT", "14031")
    TARGET_ADDRESS = f"{TARGET_HOST}:{TARGET_PORT}"
    
    OUTPUT_FILE = os.getenv("TEST_OUTPUT_FILE", "tests/output/grpc_test_audio.wav")

    logger.info(f"🔌 Connecting to gRPC Service at: {TARGET_ADDRESS}")

    try:
        with grpc.insecure_channel(TARGET_ADDRESS) as channel:
            # DÜZELTME: Stub sınıfı
            stub = coqui_pb2_grpc.TtsCoquiServiceStub(channel)
            
            # DÜZELTME: Request sınıfı ve alanlar
            request = coqui_pb2.CoquiSynthesizeRequest(
                text="Merhaba Sentiric ekibi. Bu bir Coqui motoru testidir.",
                language_code="tr",
                # Opsiyonel parametreler
                speed=1.0,
                temperature=0.75
            )

            logger.info("📤 Sending CoquiSynthesize Request...")
            start_time = time.time()

            # DÜZELTME: Metod çağrısı
            response = stub.CoquiSynthesize(request)
            
            duration = time.time() - start_time
            logger.info(f"📥 Response Received in {duration:.3f}s")

            # 5. Çıktıyı Kaydet
            os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
            with open(OUTPUT_FILE, "wb") as f:
                f.write(response.audio_content)
            
            logger.info(f"✅ Audio saved to: {OUTPUT_FILE}")
            logger.info(f"📊 Audio Size: {len(response.audio_content)} bytes")

    except grpc.RpcError as e:
        logger.error(f"❌ gRPC Error: {e.code()} - {e.details()}")
        exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected Error: {e}")
        exit(1)

if __name__ == "__main__":
    run_test()