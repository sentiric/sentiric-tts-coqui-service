# 🎙️ Sentiric Coqui TTS Service (Expert TTS Engine)

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)

**Sentiric Coqui TTS Service**, `sentiric-tts-gateway-service` tarafından yönetilen **uzman ses motorlarından** biridir. Temel görevi, Coqui XTTS-v2 modelini kullanarak yüksek kaliteli, çok dilli ve klonlanabilir sesler üretmektir.

Bu servis, özellikle sıfırdan ses klonlama (zero-shot voice cloning) yeteneği gerektiren senaryolar için kullanılır.

## 🎯 Temel Sorumluluklar

*   **Yüksek Kaliteli Sentezleme:** `TTS.api` kütüphanesini kullanarak, verilen metni sese dönüştürür.
*   **Ses Klonlama:** Gelen istekte bir `speaker_wav_url` belirtilirse, bu URL'deki sesi referans alarak klonlanmış bir ses üretir.
*   **API Sunucusu:** `tts-gateway`'den gelen `/api/v1/synthesize` isteklerini işleyen bir FastAPI sunucusu barındırır.

## 🛠️ Teknoloji Yığını

*   **Dil:** Python
*   **Web Çerçevesi:** FastAPI
*   **AI Motoru:** Coqui XTTS-v2 (`TTS` kütüphanesi)
*   **Gözlemlenebilirlik:** Prometheus metrikleri ve `structlog` ile yapılandırılmış loglama.

## 🔌 API Etkileşimleri

*   **Gelen (Sunucu):**
    *   `sentiric-tts-gateway-service` (REST/JSON): Ses sentezleme isteklerini alır.
*   **Giden (İstemci):**
    *   Harici URL'ler (HTTP): Dinamik `speaker_wav_url`'leri indirmek için.

## 🚀 Yerel Geliştirme

1.  **Bağımlılıkları Yükleyin:** `pip install -e ".[dev]"`
2.  **Servisi Başlatın:** `uvicorn app.main:app --reload --port 14030` (veya `.env` dosyanızdaki port)

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Lütfen projenin ana [Sentiric Governance](https://github.com/sentiric/sentiric-governance) reposundaki kodlama standartlarına ve katkıda bulunma rehberine göz atın.

---
## 🏛️ Anayasal Konum

Bu servis, [Sentiric Anayasası'nın (v11.0)](https://github.com/sentiric/sentiric-governance/blob/main/docs/blueprint/Architecture-Overview.md) **Zeka & Orkestrasyon Katmanı**'nda yer alan merkezi bir bileşendir.