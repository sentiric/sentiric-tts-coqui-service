import requests
import os
from rich.console import Console

console = Console()
API_URL = "http://localhost:14030"
OUTPUT_FILE = "tests/test_stream_capture.wav"

def record_stream():
    console.print(f"[bold cyan]🎙️ Stream Kayıt Testi Başlıyor...[/bold cyan]")
    
    payload = {
        "text": "Bu test, cızırtısız ve berrak bir ses için yapılıyor. Eğer bunu duyuyorsan backend tam cümleyi gönderiyor demektir.",
        "language": "tr",
        "stream": True,
        "speaker_idx": "Ana Florence",
        # PCM yerine WAV header'lı stream alalım ki direkt çalınabilsin
        # (Normalde stream raw gelir ama testimiz kolay olsun diye wav istiyoruz backend'den)
        "output_format": "wav" 
    }

    try:
        with requests.post(f"{API_URL}/api/tts", json=payload, stream=True) as r:
            if r.status_code != 200:
                console.print(f"[red]❌ Hata: {r.status_code}[/red]")
                return

            with open(OUTPUT_FILE, "wb") as f:
                console.print("   📥 Veri indiriliyor...", end="")
                total_bytes = 0
                for chunk in r.iter_content(chunk_size=None):
                    if chunk:
                        f.write(chunk)
                        total_bytes += len(chunk)
                console.print(f" [green]Bitti.[/green]")
                console.print(f"   💾 Kaydedildi: {OUTPUT_FILE} ({total_bytes} bytes)")
                
    except Exception as e:
        console.print(f"[red]❌ Bağlantı hatası: {e}[/red]")

if __name__ == "__main__":
    record_stream()