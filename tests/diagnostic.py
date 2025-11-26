import requests
import json
import numpy as np
import soundfile as sf
import io
import os
import time

# --- AYARLAR ---
API_URL = "http://localhost:14030"
OUTPUT_DIR = "tests/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def analyze_audio_data(audio_data, name):
    try:
        with io.BytesIO(audio_data) as f:
            data, samplerate = sf.read(f)
        
        max_amp = np.max(np.abs(data))
        is_clipping = max_amp >= 0.99
        
        silence_duration_samples = int(0.2 * samplerate)
        start_energy = np.mean(np.abs(data[:silence_duration_samples]))
        has_silence_padding = start_energy < 0.01

        print(f"\n🔍 ANALİZ: {name}")
        print(f"   ⏱️ Süre: {len(data)/samplerate:.2f} sn")
        print(f"   🔊 Max Genlik: {max_amp:.4f} {'(⚠️ PATLIYOR!)' if is_clipping else '✅ Temiz'}")
        print(f"   🤫 Başlangıç Enerjisi: {start_energy:.6f} {'(Backend Sessizliği Var)' if has_silence_padding else '(Saf Ses - Client Buffering Gerekli)'}")
        
        return True
    except Exception as e:
        print(f"❌ Analiz Hatası ({name}): {e}")
        return False

def test_stream_protocol():
    print("\n🧪 TEST 1: STREAM PROTOKOLÜ (Veri Akışı)")
    
    payload = {"text": "Test", "language": "tr", "stream": True, "speaker_idx": "Ana Florence"}
    
    try:
        with requests.post(f"{API_URL}/api/tts", json=payload, stream=True) as r:
            chunk_count = 0
            first_chunk_has_data = False
            
            print("   Paketler inceleniyor...")
            for chunk in r.iter_content(chunk_size=None):
                if chunk:
                    chunk_count += 1
                    arr = np.frombuffer(chunk, dtype=np.int16)
                    if chunk_count == 1:
                        # İlk pakette veri var mı?
                        if np.max(np.abs(arr)) > 0:
                            first_chunk_has_data = True
                    
                    if chunk_count > 5: break 
            
            # ARTIK BEKLENTİ: Veri gelmesi iyidir (Hızlı tepki). 
            # Sessizlik yönetimini Client (JS) tarafına taşıdık.
            if chunk_count > 0:
                print(f"   ✅ BAŞARILI: Stream veri akıtıyor. (İlk pakette veri var: {first_chunk_has_data})")
                print("   ℹ️  Not: Backend 'Raw Stream' gönderiyor. Cutoff koruması Client tarafındadır.")
            else:
                print("   ❌ HATA: Hiç veri gelmedi!")

    except Exception as e:
        print(f"   ❌ Bağlantı Hatası: {e}")

def test_normal_wav():
    print("\n🧪 TEST 2: NORMAL WAV (FFmpeg Filtreleri)")
    payload = {"text": "Merhaba dünya.", "language": "tr", "stream": False, "speaker_idx": "Ana Florence"}
    start = time.time()
    r = requests.post(f"{API_URL}/api/tts", json=payload)
    if r.status_code == 200:
        print(f"   ✅ Yanıt alındı ({time.time() - start:.2f}s). Boyut: {len(r.content)} bytes")
        path = os.path.join(OUTPUT_DIR, "test_normal.wav")
        with open(path, "wb") as f: f.write(r.content)
        analyze_audio_data(r.content, "Normal WAV")
    else:
        print(f"   ❌ API Hatası: {r.text}")

if __name__ == "__main__":
    print("🔬 SENTIRIC TTS DİYAGNOSTİK ARACI v1.2 (Updated Expectation)")
    print("=======================================")
    try: requests.get(f"{API_URL}/health", timeout=2)
    except: print("❌ Sunucu yok."); exit(1)
    test_stream_protocol()
    test_normal_wav()
    print("\n✅ Test Tamamlandı.")