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
    """Ses verisinin matematiğini inceler"""
    try:
        # Byte verisini numpy dizisine çevir
        with io.BytesIO(audio_data) as f:
            data, samplerate = sf.read(f)
        
        # 1. CLIPPING ANALİZİ (Ses Patlaması)
        max_amp = np.max(np.abs(data))
        is_clipping = max_amp >= 0.99
        
        # 2. BAŞLANGIÇ SESSİZLİĞİ (Cutoff Analizi)
        # İlk 0.2 saniyedeki ortalama enerjiye bak
        silence_duration_samples = int(0.2 * samplerate)
        start_energy = np.mean(np.abs(data[:silence_duration_samples]))
        has_silence_padding = start_energy < 0.01  # %1'den az ses varsa sessizdir

        print(f"\n🔍 ANALİZ: {name}")
        print(f"   ⏱️ Süre: {len(data)/samplerate:.2f} sn")
        print(f"   🔊 Max Genlik: {max_amp:.4f} {'(⚠️ PATLIYOR/CLIPPING!)' if is_clipping else '✅ Temiz'}")
        print(f"   🤫 Başlangıç Enerjisi: {start_energy:.6f} {'✅ Güvenli Sessizlik' if has_silence_padding else '⚠️ DİKKAT: Ses hemen başlıyor (Yutulabilir)'}")
        
        return True
    except Exception as e:
        print(f"❌ Analiz Hatası ({name}): {e}")
        return False

def test_stream_protocol():
    """Stream akışının ilk paketlerini bayt bayt inceler"""
    print("\n🧪 TEST 1: STREAM PROTOKOLÜ (Sessizlik Öncüsü)")
    
    payload = {
        "text": "Test",
        "language": "tr",
        "stream": True,
        "speaker_idx": "Ana Florence"
    }
    
    try:
        with requests.post(f"{API_URL}/api/tts", json=payload, stream=True) as r:
            chunk_count = 0
            zero_chunks = 0
            total_bytes = 0
            
            print("   Paketler inceleniyor...")
            for chunk in r.iter_content(chunk_size=None):
                if chunk:
                    chunk_count += 1
                    total_bytes += len(chunk)
                    
                    # İlk 5 paketin tamamen "0" (sessizlik) olmasını bekliyoruz
                    if chunk_count <= 5:
                        # Baytları numpy array'e çevirip bak
                        # int16 PCM verisi (Little Endian)
                        arr = np.frombuffer(chunk, dtype=np.int16)
                        if np.all(arr == 0):
                            zero_chunks += 1
                            # print(f"   Paket {chunk_count}: ✅ Tamamen Sessiz ({len(chunk)} bytes)")
                        else:
                            print(f"   Paket {chunk_count}: ⚠️ Veri içeriyor! (Max: {np.max(np.abs(arr))})")
                    
                    if chunk_count > 20: break # Test için yeterli
            
            print(f"   Sonuç: İlk 5 paketin {zero_chunks} tanesi %100 sessiz.")
            if zero_chunks >= 3:
                print("   ✅ BAŞARILI: Stream 'Preamble' (Öncü Sessizlik) çalışıyor.")
            else:
                print("   ❌ HATA: Stream direkt ses ile başlıyor (Cutoff riski yüksek).")

    except Exception as e:
        print(f"   ❌ Bağlantı Hatası: {e}")

def test_normal_wav():
    """Normal WAV üretimini ve FFmpeg filtrelerini test eder"""
    print("\n🧪 TEST 2: NORMAL WAV (FFmpeg Filtreleri)")
    
    payload = {
        "text": "Merhaba dünya, bu bir ses testidir.",
        "language": "tr",
        "stream": False, # Normal mod
        "speaker_idx": "Ana Florence"
    }
    
    start = time.time()
    r = requests.post(f"{API_URL}/api/tts", json=payload)
    dur = time.time() - start
    
    if r.status_code == 200:
        print(f"   ✅ Yanıt alındı ({dur:.2f}s). Boyut: {len(r.content)} bytes")
        path = os.path.join(OUTPUT_DIR, "test_normal.wav")
        with open(path, "wb") as f: f.write(r.content)
        
        analyze_audio_data(r.content, "Normal WAV")
    else:
        print(f"   ❌ API Hatası: {r.text}")

if __name__ == "__main__":
    print("🔬 SENTIRIC TTS DİYAGNOSTİK ARACI v1.0")
    print("=======================================")
    
    # Sunucu ayakta mı?
    try:
        requests.get(f"{API_URL}/health", timeout=2)
    except:
        print("❌ Sunucuya ulaşılamıyor. Docker çalışıyor mu?")
        exit(1)

    test_stream_protocol()
    test_normal_wav()
    print("\n✅ Test Tamamlandı.")