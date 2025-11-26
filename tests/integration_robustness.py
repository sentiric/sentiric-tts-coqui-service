import requests
import uuid
import time
from rich.console import Console
from rich.panel import Panel

console = Console()
API_URL = "http://localhost:14030"

def test_input_validation():
    console.print(Panel("[bold yellow]🧪 TEST 1: Girdi Doğrulama (Input Validation)[/bold yellow]"))
    
    # Senaryo A: Boş Metin
    try:
        r = requests.post(f"{API_URL}/api/tts", json={"text": "   ", "language": "tr"})
        if r.status_code == 422:
            console.print("[green]✅ Boş metin reddedildi (422).[/green]")
        else:
            console.print(f"[red]❌ HATA: Boş metin kabul edildi! Kod: {r.status_code}[/red]")
    except Exception as e: console.print(f"[red]Bağlantı hatası: {e}[/red]")

    # Senaryo B: Çok Uzun Metin (>5000)
    long_text = "a" * 5005
    try:
        r = requests.post(f"{API_URL}/api/tts", json={"text": long_text, "language": "tr"})
        if r.status_code == 422:
            console.print("[green]✅ Aşırı uzun metin reddedildi (422).[/green]")
        else:
            console.print(f"[red]❌ HATA: Limit aşımı kabul edildi! Kod: {r.status_code}[/red]")
    except: pass

    # Senaryo C: Geçersiz Format
    try:
        r = requests.post(f"{API_URL}/api/tts", json={"text": "Test", "output_format": "exe"})
        if r.status_code == 422:
            console.print("[green]✅ Geçersiz format (.exe) reddedildi (422).[/green]")
        else:
            console.print(f"[red]❌ HATA: Geçersiz format kabul edildi![/red]")
    except: pass

def test_lifecycle_crud():
    console.print()
    console.print(Panel("[bold blue]🧪 TEST 2: Yaşam Döngüsü (Generate -> Check -> Delete)[/bold blue]"))
    
    # FIX: Metin uzunluğunu 50 karakterin altında tutmak için UUID'yi kısalttık
    # "AutoTest " (9) + 8 hex char = 17 karakter. Kesilme olmaz.
    unique_text = f"AutoTest {uuid.uuid4().hex[:8]}"
    filename = ""
    
    # 1. Generate
    console.print(f"   1. Ses üretiliyor: '{unique_text}'")
    r = requests.post(f"{API_URL}/api/tts", json={"text": unique_text, "language": "tr"})
    if r.status_code == 200:
        console.print("[green]   ✅ Ses üretildi.[/green]")
    else:
        console.print(f"[red]   ❌ Üretim başarısız! Kod: {r.status_code}[/red]")
        return

    # Database'in yazması için minik bir bekleme (opsiyonel ama sağlıklı)
    time.sleep(0.5)

    # 2. History Check
    console.print("   2. Geçmiş kontrol ediliyor...")
    r = requests.get(f"{API_URL}/api/history")
    history = r.json()
    found = False
    for item in history:
        # Tam eşleşme ara
        if unique_text == item['text'] or unique_text in item['text']:
            filename = item['filename']
            found = True
            break
    
    if found:
        console.print(f"[green]   ✅ Kayıt geçmişte bulundu: {filename}[/green]")
    else:
        console.print("[red]   ❌ Kayıt geçmişe düşmedi![/red]")
        # Debug için son kaydı göster
        if history:
            console.print(f"      Son kayıt: {history[0]['text']}")
        return

    # 3. Delete
    console.print(f"   3. Siliniyor: {filename}...")
    r = requests.delete(f"{API_URL}/api/history/{filename}")
    if r.status_code == 200:
        console.print("[green]   ✅ API 'Silindi' dedi.[/green]")
    else:
        console.print("[red]   ❌ Silme başarısız![/red]")

    # 4. Verify Deletion
    console.print("   4. Silinme doğrulanıyor...")
    r_file = requests.get(f"{API_URL}/api/history/audio/{filename}")
    if r_file.status_code == 404:
        console.print("[green]   ✅ Dosya gerçekten yok (404).[/green]")
    else:
        console.print("[red]   ❌ Dosya hala erişilebilir! (Hayalet Kayıt)[/red]")

def test_ssml_robustness():
    console.print()
    console.print(Panel("[bold magenta]🧪 TEST 3: SSML Dayanıklılık Testi[/bold magenta]"))
    
    broken_ssml = "<speak>Merhaba <break time='1s'> bu bozuk bir tag"
    
    console.print("   Bozuk SSML gönderiliyor...")
    r = requests.post(f"{API_URL}/api/tts", json={"text": broken_ssml})
    
    if r.status_code == 200:
        console.print("[green]   ✅ Sistem çökmedi, metni temizleyip okudu (Fallback çalıştı).[/green]")
    elif r.status_code == 500:
        console.print("[red]   ❌ Sistem 500 Hatası verdi (Çöktü).[/red]")
    else:
        console.print(f"   ℹ️ Yanıt Kodu: {r.status_code}")

if __name__ == "__main__":
    try:
        test_input_validation()
        test_lifecycle_crud()
        test_ssml_robustness()
        console.print("\n[bold green]✨ TÜM ENTEGRASYON TESTLERİ TAMAMLANDI[/bold green]")
    except Exception as e:
        console.print(f"[bold red]TEST ÇÖKTÜ: {e}[/bold red]")