# 1. Sanal ortam oluştur
python3 -m venv .venv_test

# 2. Ortamı aktif et
source .venv_test/bin/activate

# 3. Bağımlılıkları kur
pip install requests rich soundfile numpy

python3 tests/benchmark.py

python3 tests/diagnostic.py

python3 tests/integration_robustness.py

python3 tests/test_stream_recording.py