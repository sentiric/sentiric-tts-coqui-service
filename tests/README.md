---
**[MİMARİ KARAR VE ANALİZ]**
*   **Sorun:** Modern Linux dağıtımları (Ubuntu 24.04+ / Debian 12+), sistem bütünlüğünü korumak için `pip` ile global paket kurulumunu engeller (PEP 668).
*   **Çözüm:** Benchmark için izole bir **Virtual Environment (Sanal Ortam)** oluşturacağız. Bu, sistem dosyalarına dokunmadan gerekli kütüphaneleri kurmamızı sağlar.

**[UYGULAMA]**

Aşağıdaki komutları sırasıyla terminale yapıştır. Bu işlem sanal bir alan yaratır, test paketlerini oraya kurar ve testi çalıştırır.

```bash
# 1. Sanal ortam oluştur (Sadece test için)
python3 -m venv .venv_test

# 2. Sanal ortamı aktif et
source .venv_test/bin/activate

# 3. Gerekli paketleri bu izole ortama kur
pip install requests rich soundfile numpy

# 4. Benchmark testini çalıştır
python3 tests/benchmark.py
```
