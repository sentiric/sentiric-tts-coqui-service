# Dosya: TASKS.md
- [x] Sentiric Architecture Spec entegrasyonu tamamlandı (`tts-coqui-service`).
- [x] **Mimari İhlal Giderildi:** `grpc_server.py` içerisinde TLS sertifikası bulunamadığında devreye giren güvensiz (insecure port) fallback mekanizması tamamen kaldırıldı. Spesifikasyon (constraints.yaml) uyarınca mTLS bağlantısı **kesin zorunlu** (strict) hale getirildi.