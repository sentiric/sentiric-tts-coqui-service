# Sentiric TTS Test Suite

Bu dizin, Sentiric TTS servisinin performansını, kararlılığını ve doğruluğunu ölçmek için kullanılan otomatik test araçlarını içerir.

## Ön Hazırlık (Sanal Ortam)

Modern Linux dağıtımlarında sistem paketlerini korumak için testleri izole bir ortamda çalıştırmanız önerilir.

```bash
# 1. Sanal ortam oluştur
python3 -m venv .venv_test

# 2. Ortamı aktif et
source .venv_test/bin/activate

# 3. Bağımlılıkları kur
pip install requests rich soundfile numpy
```

## Test Araçları

### 1. Performans Benchmark'ı (`benchmark.py`)
Sistemin hızını (RTF), gecikmesini (Latency) ve yük altındaki dayanıklılığını ölçer.

*   **Komut:** `python3 tests/benchmark.py`
*   **Çıktı:** Konsol grafikleri ve `benchmark_report.md` dosyası.
*   **Kullanım:** Sunucu optimizasyonlarından sonra hızın düşüp düşmediğini kontrol etmek için.

### 2. Diyagnostik Araç (`diagnostic.py`)
Ses kalitesini ve protokol bütünlüğünü matematiksel olarak analiz eder.

*   **Komut:** `python3 tests/diagnostic.py`
*   **Kontroller:**
    *   **Clipping:** Ses patlaması var mı? (Max Genlik > 0.99)
    *   **Cutoff:** Başlangıçta sessizlik var mı? (Start Energy < 0.01)
    *   **Stream Protocol:** İlk paketler boş mu? (Preamble Check)

### 3. Entegrasyon ve Dayanıklılık (`integration_robustness.py`)
API'nin hata yönetimi ve veri bütünlüğünü test eder.

*   **Komut:** `python3 tests/integration_robustness.py`
*   **Senaryolar:**
    *   Boş veya aşırı uzun metin gönderme (422 Hatası beklenir).
    *   Ses üretme, geçmişte bulma ve silme (CRUD Döngüsü).
    *   Bozuk SSML tagleri gönderme (Sistemin çökmemesi beklenir).


---

python3 tests/test_stream_recording.py

---

## Örnek Rapor

```text
🧪 TEST 1: Girdi Doğrulama
✅ Boş metin reddedildi (422).
✅ Aşırı uzun metin reddedildi (422).

🧪 TEST 2: Yaşam Döngüsü
✅ Ses üretildi.
✅ Kayıt geçmişte bulundu.
✅ API 'Silindi' dedi.
✅ Dosya gerçekten yok (404).
```
