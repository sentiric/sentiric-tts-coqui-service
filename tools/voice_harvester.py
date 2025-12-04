import os
import time
from gtts import gTTS
from pydub import AudioSegment

# --- AYARLAR ---
OUTPUT_DIR = "speakers"
# Google'dan çekilecek referans sesler
# Format: "Klasör_Adi": {"lang": "dil_kodu", "samples": {"stil": "okunacak metin"}}
# Not: Google TTS'de duygu yoktur ama tonlama farkı yaratmak için noktalama işaretleri kullanacağız.

VOICE_MAP = {
    "F_Assistant_Judy": {
        "lang": "en",
        "tld": "us", # Amerikan Aksanı
        "samples": {
            "neutral": "Hello, I am ready to assist you with your tasks today.",
            "happy": "Wow! That is absolutely amazing news, I am so excited!",
            "sad": "I am sorry to hear that, it is very unfortunate...",
            "angry": "I cannot believe you did that! It is unacceptable!"
        }
    },
    "M_Narrator_Bill": {
        "lang": "en",
        "tld": "co.uk", # İngiliz Aksanı
        "samples": {
            "neutral": "The history of the universe is vast and complex.",
            "happy": "And then, suddenly, the sun came out and everyone cheered!",
            "sad": "The old house stood empty, memories fading into the dust.",
            "angry": "Stop right there! You are not allowed to enter this area!"
        }
    },
    "F_Turkish_Ece": {
        "lang": "tr",
        "tld": "com.tr",
        "samples": {
            "neutral": "Merhaba, Sentiric sistemine hoş geldiniz. İşlemleriniz yapılıyor.",
            "happy": "Harika! Bunu başardığımıza inanamıyorum, çok mutluyum!",
            "sad": "Maalesef işleminiz başarısız oldu, lütfen tekrar deneyin.",
            "angry": "Bu hata kabul edilemez! Derhal düzeltilmesi gerekiyor!"
        }
    }
}

def harvest_voices():
    print("🌾 SENTIRIC VOICE HARVESTER BAŞLATILIYOR...")
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    for speaker, config in VOICE_MAP.items():
        print(f"🎙️  İşleniyor: {speaker} ({config['lang']})")
        
        spk_dir = os.path.join(OUTPUT_DIR, speaker)
        os.makedirs(spk_dir, exist_ok=True)
        
        for style, text in config['samples'].items():
            filename = f"{style}.wav"
            filepath = os.path.join(spk_dir, filename)
            
            try:
                # 1. Google'dan MP3 olarak çek
                tts = gTTS(text=text, lang=config['lang'], tld=config.get('tld', 'com'), slow=False)
                mp3_path = filepath.replace(".wav", ".mp3")
                tts.save(mp3_path)
                
                # 2. WAV formatına çevir (XTTS için gerekli)
                sound = AudioSegment.from_mp3(mp3_path)
                # Mono ve 22050Hz/24000Hz (Standartlaştırma)
                sound = sound.set_channels(1).set_frame_rate(24000)
                sound.export(filepath, format="wav")
                
                # Temizlik
                os.remove(mp3_path)
                print(f"   ✅ Oluşturuldu: {style}")
                
                # Google'ı banlamaması için bekleme
                time.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Hata ({style}): {e}")

    print("\n✨ Hasat Tamamlandı! Lütfen bu klasörü Docker içindeki '/app/speakers' yoluna mount edin.")

if __name__ == "__main__":
    # Pydub için ffmpeg kontrolü
    try:
        harvest_voices()
    except ImportError:
        print("⚠️ GEREKSİNİMLER EKSİK!")
        print("Lütfen şunları kurun: pip install gTTS pydub")
        print("Ayrıca sisteminizde FFmpeg kurulu olmalıdır.")