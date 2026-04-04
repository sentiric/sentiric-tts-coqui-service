# 🗣️ Sentiric TTS Coqui Service

[![Production Ready](https://img.shields.io/badge/status-production%20ready-success.svg)]()
[![Architecture](https://img.shields.io/badge/arch-Python_CUDA-blue.svg)]()

**Sentiric XTTS**, Coqui XTTS v2 modelini temel alan, yüksek hızlı Streaming (Akış), Deterministic Caching ve Dynamic Fade-Out (Sönümleme) optimizasyonlarına sahip uçtan uca ses sentezleme motorudur.

## 🚀 Hızlı Başlangıç

### 1. Çalıştırma (Docker - GPU Önerilir)
```bash
docker compose -f docker-compose.standalone.yml up -d --build
```

### 2. Doğrulama (Health Check)
```bash
curl http://localhost:14030/health
```

## 🏛️ Mimari Anayasa ve Kılavuzlar
* **Kodlama Kuralları (AI/İnsan):** Bu repoda geliştirmeye başlamadan önce GİZLİ [.context.md](.context.md) dosyasını okuyun.
* **Ses Algoritmaları (DSP & Cache):** Smart GC, Mathematical Fade-out ve MD5 Hash algoritmaları için [LOGIC.md](LOGIC.md) dosyasını inceleyin.
* **Sistem Sınırları ve Topoloji:** Bu servisin platformdaki konumu ve dış bağlantıları **[sentiric-spec](https://github.com/sentiric/sentiric-spec)** anayasasında tanımlıdır.
