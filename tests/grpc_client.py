import os
import grpc
import logging
import time
from sentiric.tts.v1 import coqui_pb2, coqui_pb2_grpc

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("TEST-CLIENT")

def run_test():
    TARGET_HOST = os.getenv("TTS_SERVICE_HOST", "localhost")
    TARGET_PORT = os.getenv("TTS_SERVICE_PORT", "14031")
    TARGET_ADDRESS = f"{TARGET_HOST}:{TARGET_PORT}"
    
    # DÜZELTME: /tmp dizinini kullan
    OUTPUT_DIR = "/tmp/sentiric-tts-tests"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, "grpc_test_audio.wav")

    logger.info(f"🔌 Connecting to gRPC Service at: {TARGET_ADDRESS}")
    try:
        with grpc.insecure_channel(TARGET_ADDRESS) as channel:
            stub = coqui_pb2_grpc.TtsCoquiServiceStub(channel)
            request = coqui_pb2.CoquiSynthesizeRequest(
                text="Merhaba Sentiric ekibi. Bu bir Coqui motoru gRPC testidir.",
                language_code="tr",
                speed=1.0, temperature=0.75
            )
            logger.info("📤 Sending CoquiSynthesize Request...")
            start_time = time.time()
            response = stub.CoquiSynthesize(request)
            duration = time.time() - start_time
            logger.info(f"📥 Response Received in {duration:.3f}s")

            if len(response.audio_content) < 1000:
                logger.error("❌ gRPC response audio is empty or too short!")
                exit(1)

            with open(OUTPUT_FILE, "wb") as f:
                f.write(response.audio_content)
            
            logger.info(f"✅ Audio saved to: {OUTPUT_FILE}")

    except grpc.RpcError as e:
        logger.error(f"❌ gRPC Error: {e.code()} - {e.details()}")
        exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected Error: {e}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    run_test()