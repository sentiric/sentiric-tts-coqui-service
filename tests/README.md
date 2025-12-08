# Sentiric TTS Test Suite

Bu dizin, Sentiric TTS servisinin performansını, kararlılığını ve doğruluğunu ölçmek için kullanılan otomatik test araçlarını içerir.

## Ön Hazırlık (Sanal Ortam)

Modern Linux dağıtımlarında sistem paketlerini korumak için testleri izole bir ortamda çalıştırmanız önerilir.

```bash
# 1. Sanal ortam oluştur (zaten varsa bu adımı atla)
python3 -m venv .venv_test

# 2. Ortamı aktif et
source .venv_test/bin/activate

# 3. Bağımlılıkları kur (gRPC dahil)
pip install requests rich soundfile numpy grpcio "sentiric-contracts-py @ git+https://github.com/sentiric/sentiric-contracts.git@v1.12.0"
```

## Test Araçları

### 1. Performans Benchmark'ı (`benchmark.py`)
Sistemin hızını (RTF), gecikmesini (Latency) ve yük altındaki dayanıklılığını ölçer.

*   **Komut:** `python3 tests/benchmark.py`
*   **Çıktı:** Konsol grafikleri ve `tests/output/benchmark_report.md` dosyası.
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

### 4. gRPC İstemci Testi (`grpc_client.py`)
gRPC endpoint'inin doğru çalışıp çalışmadığını kontrol eder.

*   **Komut:** `python3 tests/grpc_client.py`
*   **Çıktı:** `tests/output/grpc_test_audio.wav` dosyası.
