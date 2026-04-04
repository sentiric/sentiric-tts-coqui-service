# 🧬 Domain Logic & Ses İşleme Algoritmaları

Bu belge, `sentiric-tts-coqui-service`'in saf XTTS modelinden ayrılarak nasıl "Stüdyo Kalitesinde" (Artifact-Free) ve sıfır gecikmeli bir sunucuya dönüştüğünü sağlayan kritik algoritmaları açıklar.

## 1. Look-Ahead Buffering ve Mathematical Fade-Out
* **Sorun:** Standart TTS streaming motorlarında, ses parçaları (chunk) üretildikçe cümlenin en sonunda "pıt", "tıss" gibi kopma sesleri (Audio Artifacts) oluşur.
* **Algoritma:** Sistem, stream edilen ses paketlerini bir adım geriden takip eder. Son paketin geldiği anlaşıldığında, paket ağa gönderilmeden önce NumPy tensörü üzerinde bir maskeleme yapılır. Ses eşik değerinin altındaysa (`threshold=0.025`), son `N` örneğe doğrusal bir matematiksel eğri (`np.linspace(1.0, 0.0)`) uygulanarak ses pürüzsüzce sönümlenir (Fade-out).

## 2. Deterministic Caching (MD5 Based Zero-Latency)
* **Sorun:** Gelen metin tamamen aynı olsa bile eski sistemler UUID kullandığı için GPU her seferinde boş yere çalışır (RTF > 0.3).
* **Algoritma:** Gelen istek parametrelerinin (Metin + Dil + Speaker_Idx + Hız + Sıcaklık) tamamı json olarak sıralanıp (sort_keys=True) deterministik bir **MD5 Hash** üretilir.
* **Sonuç:** Eğer bu Hash diskin `cache/` klasöründe mevcutsa, GPU hiç tetiklenmez. Dosya doğrudan okunur ve `0.0007` RTF değeri ile (neredeyse 0ms gecikme) HTTP/gRPC üzerinden geri dönülür.

## 3. Smart VRAM Garbage Collector
* **Algoritma:** `SmartMemoryManager` sınıfı, GPU belleğini sürekli izler. Sadece VRAM ayrılmış belleği `4500MB` sınırını aştığında veya her `10` istekte bir periyodik olarak `gc.collect()` ve `torch.cuda.empty_cache()` çağırır. Bu agresif olmayan yaklaşım, sürekli önbellek temizliğinin yarattığı darboğazı engeller.

## 4. SSML Plain-Text Fallback
* **Algoritma:** Kullanıcıdan gelen `<speak>` etiketli metinler `defusedxml` ile parçalanırken (Parse) bir XML format hatası olursa sistem 500 kodu dönüp çökmez. Hemen Regex (Regular Expression) fallback moduna geçer, XML etiketlerini temizler ve ham metni (Plain Text) sentezleyerek kesintisiz iletişimi garanti eder.
