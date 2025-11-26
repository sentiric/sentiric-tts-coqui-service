import requests
import soundfile as sf
import numpy as np
import io
from rich.console import Console

console = Console()
API_URL = "http://localhost:14030"
OUTPUT_FILE = "tests/test_stream_capture.wav"

def record_stream():
    console.print(f"[bold cyan]🎙️ Stream Kayıt Testi Başlıyor...[/bold cyan]")
    
    payload = {
        "text": "Bu ses kaydı, sistemin cızırtısız çalıştığını kanıtlamak için yapılmıştır. Lütfen dikkatlice dinleyin.",
        "language": "tr",
        "stream": True,
        "speaker_idx": "Ana Florence"
    }

    raw_audio_buffer = io.BytesIO()

    try:
        with requests.post(f"{API_URL}/api/tts", json=payload, stream=True) as r:
            if r.status_code != 200:
                console.print(f"[red]❌ Hata: {r.status_code}[/red]")
                return

            console.print("   📥 Veri indiriliyor...", end="")
            for chunk in r.iter_content(chunk_size=None):
                if chunk:
                    raw_audio_buffer.write(chunk)
            console.print(f" [green]Bitti.[/green]")

        # RAW PCM verisini numpy array'e çevir
        raw_data = raw_audio_buffer.getvalue()
        # int16 formatında (XTTS standardı)
        audio_np = np.frombuffer(raw_data, dtype=np.int16)

        # SoundFile ile Header ekleyerek kaydet (24000Hz)
        sf.write(OUTPUT_FILE, audio_np, 24000)
        
        console.print(f"   💾 Dosya oluşturuldu: [bold]{OUTPUT_FILE}[/bold]")
        console.print(f"   ℹ️  Bu dosyayı bilgisayarına indirip dinle. Cızırtı var mı?")

    except Exception as e:
        console.print(f"[red]❌ Hata: {e}[/red]")

if __name__ == "__main__":
    record_stream()