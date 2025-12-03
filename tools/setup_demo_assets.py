import os
import shutil
import glob

# Hedef klasör (Container içindeki yol)
SPEAKERS_DIR = "../sentiric-assets/docs/audio/speakers/en"
# Demo için oluşturulacak stiller
DEMO_STYLES = ["neutral", "happy", "sad", "angry", "whisper"]

def migrate_speakers():
    print(f"🚀 Başlatılıyor: Speaker Klasör Migrasyonu ({SPEAKERS_DIR})...")
    
    if not os.path.exists(SPEAKERS_DIR):
        print(f"❌ Hata: {SPEAKERS_DIR} bulunamadı.")
        return

    # Mevcut .wav dosyalarını bul
    wav_files = glob.glob(os.path.join(SPEAKERS_DIR, "*.wav"))
    
    if not wav_files:
        print("⚠️ Hiç .wav dosyası bulunamadı. Lütfen önce en az bir speaker dosyası yükleyin.")
        # Fallback dosya oluştur
        dummy_path = os.path.join(SPEAKERS_DIR, "system_default.wav")
        with open(dummy_path, 'wb') as f: f.write(b'RIFF....') # Dummy content
        wav_files = [dummy_path]

    for wav_path in wav_files:
        filename = os.path.basename(wav_path)
        speaker_name = os.path.splitext(filename)[0]
        
        # Dosya zaten bir stil dosyasımı? (klasör içindeyse atla)
        if os.path.dirname(wav_path) != SPEAKERS_DIR:
            continue

        print(f"📦 İşleniyor: {speaker_name}...")
        
        # 1. Speaker adına klasör oluştur
        target_folder = os.path.join(SPEAKERS_DIR, speaker_name)
        os.makedirs(target_folder, exist_ok=True)
        
        # 2. Orijinal dosyayı 'neutral.wav' olarak taşı/kopyala
        neutral_path = os.path.join(target_folder, "neutral.wav")
        shutil.copy2(wav_path, neutral_path)
        
        # 3. Diğer stilleri (happy, sad vs.) bu dosyadan kopyalayarak oluştur (Placeholder)
        # NOT: Gerçek hayatta buraya gerçekten mutlu/üzgün sesler konmalıdır.
        # Şimdilik sistem çalışsın diye kopyalıyoruz.
        for style in DEMO_STYLES:
            if style == "neutral": continue
            style_path = os.path.join(target_folder, f"{style}.wav")
            if not os.path.exists(style_path):
                shutil.copy2(wav_path, style_path)
        
        # 4. Kök dizindeki eski dosyayı temizle (Opsiyonel, karışıklığı önlemek için yapıyoruz)
        # os.remove(wav_path) 
        print(f"✅ {speaker_name} klasör yapısına dönüştürüldü ({len(DEMO_STYLES)} stil).")

    print("\n✨ Migrasyon Tamamlandı! Artık UI üzerinde stilleri görebilirsiniz.")
    print("👉 İPUCU: Gerçek duygu için '/app/speakers/[Ad]/happy.wav' dosyasını gerçek bir kayıtla değiştirin.")

if __name__ == "__main__":
    migrate_speakers()