# 🗣️ Sentiric XTTS Pro: Production-Ready Neural TTS Engine

[![Docker Build](https://img.shields.io/badge/docker-build-blue.svg)]()
[![Status](https://img.shields.io/badge/status-production_ready-green.svg)]()
[![License](https://img.shields.io/badge/license-AGPLv3-red.svg)]()

**Sentiric XTTS Pro**, Coqui XTTS v2 modelini temel alan, yüksek performanslı, GPU hızlandırmalı, API öncelikli bir Metinden-Sese (Text-to-Speech) mikroservisidir.

Bu repo, hem **Sentiric İletişim Platformu'nun** bir parçası olarak (Cluster Mode) hem de **tek başına** (Standalone Mode) çalışacak şekilde tasarlanmıştır.

---

## 🚀 Temel Özellikler

*   **Üretim Kalitesi:** 6GB VRAM'de bile çalışabilen, `DeepSpeed` ve `Half-Precision` optimizasyonları.
*   **Çift Modlu Çalışma:** 
    *   **Cluster Mode:** Sentiric ekosistemi içinde API Gateway arkasında çalışır.
    *   **Standalone Mode:** Kendi dahili API Key korumasıyla bağımsız bir ürün olarak çalışır.
*   **Gelişmiş Kontrol:** SSML (Duraklama, Vurgu, Hız) desteği.
*   **Çok Dilli:** Türkçe, İngilizce, Almanca, İspanyolca vb. 16 dilde sentezleme.
*   **Anlık Klonlama:** Sadece 6 saniyelik bir ses dosyasıyla herhangi bir sesi klonlayın.
*   **Streaming:** 500ms'nin altında ilk bayt süresi (TTFB) ile gerçek zamanlı akış.

---

## 📦 Kurulum ve Çalıştırma

### Yöntem 1: Sentiric Ekosistemi İçinde (Önerilen)
Eğer tam platformu kullanıyorsanız, `sentiric-infrastructure` reposundaki `make start` komutunu kullanın.

### Yöntem 2: Bağımsız Çalıştırma (Standalone)
Sadece bu TTS motorunu kendi projelerinizde kullanmak istiyorsanız:

1.  **Gereksinimler:**
    *   NVIDIA GPU (Sürücüler ve Container Toolkit kurulu olmalı)
    *   Docker & Docker Compose

2.  **Başlatma:**
    ```bash
    # 1. Repoyu klonlayın
    git clone https://github.com/sentiric/sentiric-tts-coqui-service.git
    cd sentiric-tts-coqui-service

    # 2. Standalone modunda başlatın
    docker compose -f docker-compose.standalone.yml up -d --build
    ```

3.  **Erişim:**
    *   **UI Dashboard:** [http://localhost:14030](http://localhost:14030)
    *   **Swagger API:** [http://localhost:14030/docs](http://localhost:14030/docs)
    *   **Varsayılan API Key:** `sentiric-secret-key-123` (docker-compose dosyasından değiştirin)

---

## 🛠️ API Kullanımı

### 1. Basit Konuşturma (cURL)
```bash
curl -X POST "http://localhost:14030/api/tts" \
     -H "X-API-Key: sentiric-secret-key-123" \
     -H "Content-Type: application/json" \
     -d '{
           "text": "Merhaba, bu Sentiric teknolojisinin gücüdür.",
           "language": "tr",
           "speaker_idx": "Ana Florence"
         }' \
     --output merhaba.wav
```

### 2. Ses Klonlama
```bash
curl -X POST "http://localhost:14030/api/tts/clone" \
     -H "X-API-Key: sentiric-secret-key-123" \
     -F "text=Bu benim kendi sesimle oluşturulmuş bir yapay zeka konuşmasıdır." \
     -F "language=tr" \
     -F "files=@/path/to/my_voice.wav" \
     --output clone.wav
```

### 3. OpenAI Uyumlu API (Drop-in Replacement)
Open WebUI veya benzeri araçlarla uyumludur:
```bash
curl http://localhost:14030/v1/audio/speech \
  -H "Authorization: Bearer sentiric-secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-1",
    "input": "OpenAI standardında konuşuyorum.",
    "voice": "alloy"
  }' --output openai_fmt.mp3
```

### 4. SSML Control
```xml
<speak>
    Hello <break time="1s"/> 
    <prosody rate="fast">I am speaking fast now.</prosody>
    <emphasis level="strong">This is important.</emphasis>
</speak>
```

---

## 📊 Performans Metrikleri (RTX 3060 12GB)

| Metrik | Değer | Hedef | Durum |
| :--- | :--- | :--- | :--- |
| **RTF (Real-Time Factor)** | `0.0012` | < 0.10 | 🚀 Mükemmel |
| **Latency (Streaming)** | `~450ms` | < 500ms | ✅ Başarılı |
| **VRAM Kullanımı** | `~4.2 GB` | < 6 GB | ✅ Optimize |

---

## 🔒 Güvenlik ve Lisans

*   Bu proje **Coqui CPML** lisansı altındaki XTTS v2 modelini kullanır. Ticari kullanım için Coqui lisans koşullarını inceleyiniz.
*   Kod tabanı **AGPLv3** ile lisanslanmıştır.

---
**(c) 2025 Sentiric Platform Team**