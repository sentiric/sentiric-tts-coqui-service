# 🗣️ Sentiric XTTS Ultimate: High-Performance Neural TTS Engine

[![Docker Build](https://img.shields.io/badge/docker-build-green.svg)]()
[![Status](https://img.shields.io/badge/status-production_ready-success.svg)]()
[![Latency](https://img.shields.io/badge/latency-%3C350ms-blue.svg)]()

**Sentiric XTTS Ultimate**, Coqui XTTS v2 modelini temel alan, ancak **Streaming**, **Caching** ve **Audio Processing** katmanlarında devrim niteliğinde optimizasyonlar içeren bir mikroservistir.

---

## 🚀 v2.5 Mimarisi ve Kritik İyileştirmeler

### 1. 🌊 Smart Streaming & Artifact Removal
Standart TTS motorları stream sırasında cümlenin sonunda "pıt", "tıss" veya nefes alma sesleri bırakır.
*   **Çözüm:** `Look-Ahead Buffering` mimarisi.
*   **Nasıl Çalışır:** Sistem, stream edilen ses paketlerini bir adım geriden takip eder. Son paketin geldiğini anladığı anda, paketi göndermeden önce **Matematiksel Fade-Out (Sönümleme)** uygular.
*   **Sonuç:** Bıçakla kesilmiş gibi değil, stüdyo kaydı gibi biten pürüzsüz sesler.

### 2. ⚡ Deterministic Caching (Hash-Based)
Eski sistem her istekte `uuid` ile yeni dosya oluşturuyordu.
*   **Yeni Mimari:** İstek parametrelerinin (Metin + Speaker + Hız + Sıcaklık) **MD5 Hash**'i alınır.
*   **Avantaj:** Aynı cümleyi tekrar istediğinizde, **Engine çalışmaz**. Diskten 1ms içinde yanıt döner. `RTF` değeri `0.0007` seviyesine iner.

### 3. 🛡️ 6GB VRAM Optimization (Smart GC)
Agresif bellek temizliği yerine **Akıllı Çöp Toplayıcı (Smart GC)** geliştirildi.
*   GPU belleği sadece `%85` doluluğu aştığında veya her 10 istekte bir temizlenir.
*   Bu sayede her istekte yaşanan 300ms'lik `cuda.empty_cache()` gecikmesi ortadan kalktı.

### 4. 🎹 Frontend Audio Pipeline
*   **Jitter Buffer:** Ağ dalgalanmalarına karşı ses paketleri istemci tarafında kuyruğa alınır (Gapless Playback).
*   **Valid WAV Headers:** Stream edilen ham veriler (Raw PCM), diske kaydedilirken geçerli RIFF WAV başlıkları ile paketlenir. Bu sayede "Cache Hit" durumunda tarayıcılar dosyayı hatasız çalar.

---

## 🛠️ Kurulum ve Çalıştırma

### 1. Standalone (Docker)
```bash
# Repoyu klonlayın ve başlatın
docker compose -f docker-compose.standalone.yml up -d --build
```

### 2. Erişim
*   **UI Dashboard:** [http://localhost:14030](http://localhost:14030)
*   **Swagger API:** [http://localhost:14030/docs](http://localhost:14030/docs)

---

## 📊 Performans Metrikleri (RTX 3060 12GB)

| Metrik | Eski Değer | Yeni Değer (v2.5) | İyileştirme |
| :--- | :--- | :--- | :--- |
| **TTFB (Latency)** | ~600ms | **~330ms** | 🚀 %45 Hızlanma |
| **Cache Hit RTF** | N/A | **0.0007** | ⚡ Anlık Yanıt |
| **Audio Quality** | Glitchy | **Studio Clean** | ✅ Artifact-Free |

---

## 🔒 Lisans
Bu proje **Coqui CPML** lisansı altındaki XTTS v2 modelini kullanır. Kod tabanı **AGPLv3** ile lisanslanmıştır.

**(c) 2025 Sentiric Platform Team**
