import requests
import numpy as np
import soundfile as sf
import io
import os
import time

API_URL = "http://localhost:14030"
# DÜZELTME: /tmp dizinini kullan
OUTPUT_DIR = "/tmp/sentiric-tts-tests"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def analyze_audio_data(audio_data, name):
    try:
        if len(audio_data) < 1000:
             print(f"❌ Analiz Hatası ({name}): Ses verisi çok kısa ({len(audio_data)} bytes).")
             return False
        with io.BytesIO(audio_data) as f: data, sr = sf.read(f)
        print(f"\n🔍 ANALİZ: {name} | ✅ OK")
        return True
    except Exception as e:
        print(f"❌ Analiz Hatası ({name}): {e}")
        return False

def test_stream_protocol():
    print("\n🧪 TEST 1: STREAM PROTOKOLÜ")
    payload = {"text": "Test", "language": "tr", "stream": True, "speaker_idx": "F_TR_Kurumsal_Ece"}
    try:
        with requests.post(f"{API_URL}/api/tts", json=payload, stream=True) as r:
            r.raise_for_status()
            chunk = next(r.iter_content(chunk_size=1024))
            if chunk: print("   ✅ BAŞARILI: Stream veri akıtıyor.")
            else: print("   ❌ HATA: Hiç veri gelmedi!")
    except Exception as e:
        print(f"   ❌ Bağlantı Hatası: {e}")

def test_normal_wav():
    print("\n🧪 TEST 2: NORMAL WAV")
    payload = {"text": "Merhaba dünya.", "language": "tr", "stream": False, "speaker_idx": "F_TR_Kurumsal_Ece"}
    r = requests.post(f"{API_URL}/api/tts", json=payload)
    if r.status_code == 200 and len(r.content) > 0:
        path = os.path.join(OUTPUT_DIR, "test_normal.wav")
        with open(path, "wb") as f: f.write(r.content)
        analyze_audio_data(r.content, "Normal WAV")
    else:
        print(f"   ❌ API Hatası: {r.text if r.text else f'Status: {r.status_code}, Size: {len(r.content)} bytes'}")

if __name__ == "__main__":
    print("🔬 SENTIRIC TTS DİYAGNOSTİK ARACI v1.4")
    try: 
        if requests.get(f"{API_URL}/health", timeout=2).status_code != 200: exit(1)
    except: exit(1)
    test_stream_protocol()
    test_normal_wav()
    print("\n✅ Test Tamamlandı.")