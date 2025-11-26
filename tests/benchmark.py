import time
import requests
import json
import threading
import concurrent.futures
import io
import soundfile as sf
import statistics
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from datetime import datetime

# --- CONFIGURATION ---
BASE_URL = "http://localhost:14030"
API_URL = f"{BASE_URL}/api/tts"
OUTPUT_REPORT = "benchmark_report.md"

# Test Metni (Orta uzunlukta, fonetik olarak zengin)
TEST_TEXT = "Sentiric XTTS servisi, yapay zeka tabanlı ses sentezleme teknolojilerinde yüksek performans ve düşük gecikme süresi hedefler. Bu bir performans testidir."
TEST_SPEAKER = "Ana Florence"
CONCURRENCY_LEVEL = 5  # Aynı anda kaç istek atılacak?

console = Console()
results = {
    "latency_stream": [],
    "latency_non_stream": [],
    "rtf": [],
    "errors": 0,
    "concurrency_success": 0
}

def check_health():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code == 200:
            console.print("[green]✅ Server is HEALTHY[/green]")
            return True
    except:
        console.print("[red]❌ Server is DOWN or Unreachable[/red]")
        return False

def measure_rtf():
    """Real-Time Factor ölçümü: (Ses Üretim Süresi) / (Ses Dosyası Süresi)"""
    payload = {
        "text": TEST_TEXT,
        "language": "tr",
        "speaker_idx": TEST_SPEAKER,
        "stream": False
    }
    
    start_time = time.perf_counter()
    response = requests.post(API_URL, json=payload)
    end_time = time.perf_counter()
    
    if response.status_code == 200:
        process_time = end_time - start_time
        
        # Ses süresini hesapla
        audio_data = io.BytesIO(response.content)
        data, samplerate = sf.read(audio_data)
        audio_duration = len(data) / samplerate
        
        rtf = process_time / audio_duration
        results["rtf"].append(rtf)
        results["latency_non_stream"].append(process_time)
        
        return process_time, audio_duration, rtf
    else:
        results["errors"] += 1
        return None, None, None

def measure_streaming_latency():
    """Time To First Byte (TTFB) ölçümü"""
    payload = {
        "text": "Merhaba, test başlıyor.",
        "language": "tr",
        "speaker_idx": TEST_SPEAKER,
        "stream": True
    }
    
    start_time = time.perf_counter()
    try:
        # stream=True ile isteği at, ilk chunk gelince süreyi durdur
        with requests.post(API_URL, json=payload, stream=True) as r:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    first_byte_time = time.perf_counter()
                    latency = (first_byte_time - start_time) * 1000 # ms cinsinden
                    results["latency_stream"].append(latency)
                    break # Sadece ilk chunk önemli
    except Exception as e:
        console.print(f"[red]Stream Error: {e}[/red]")
        results["errors"] += 1

def concurrency_task(id):
    """Eşzamanlılık testi için worker"""
    try:
        payload = {
            "text": f"Thread {id} rapor veriyor.",
            "language": "tr",
            "speaker_idx": TEST_SPEAKER
        }
        r = requests.post(API_URL, json=payload, timeout=30) # Queue beklentisi için timeout yüksek
        if r.status_code == 200:
            return True
    except:
        return False
    return False

def run_benchmark():
    if not check_health(): return

    console.print("\n[bold cyan]🚀 SENTIRIC XTTS PERFORMANCE BENCHMARK[/bold cyan]")
    console.print(f"Target: {BASE_URL} | Device: GPU/CPU Hybrid\n")

    # 1. WARMUP
    with console.status("[yellow]🔥 Warming up model (Loading weights)...[/yellow]"):
        measure_rtf()
        console.print("[gray]Warmup complete.[/gray]")

    # 2. RTF & LATENCY TEST
    console.print("\n[bold]1. Single Request Performance[/bold]")
    proc_time, audio_dur, rtf = measure_rtf()
    if rtf:
        console.print(f"   Generating {audio_dur:.2f}s audio took {proc_time:.2f}s")
        console.print(f"   [bold green]RTF: {rtf:.4f}[/bold green] (Lower is better, < 0.3 is target)")
    
    # 3. STREAMING LATENCY
    console.print("\n[bold]2. Streaming Latency (TTFB)[/bold]")
    measure_streaming_latency()
    lat = results["latency_stream"][-1]
    console.print(f"   Time to First Sound: [bold cyan]{lat:.0f}ms[/bold cyan]")

    # 4. CONCURRENCY STRESS TEST
    console.print(f"\n[bold]3. Concurrency Stress Test ({CONCURRENCY_LEVEL} parallel reqs)[/bold]")
    console.print("   [dim]Testing if Global Lock queues requests correctly...[/dim]")
    
    start_stress = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY_LEVEL) as executor:
        futures = [executor.submit(concurrency_task, i) for i in range(CONCURRENCY_LEVEL)]
        success_count = 0
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            task = progress.add_task("Stress Testing...", total=CONCURRENCY_LEVEL)
            for future in concurrent.futures.as_completed(futures):
                if future.result():
                    success_count += 1
                progress.advance(task)
    
    total_stress_time = time.perf_counter() - start_stress
    results["concurrency_success"] = success_count
    
    console.print(f"   Success Rate: {success_count}/{CONCURRENCY_LEVEL}")
    console.print(f"   Total Duration: {total_stress_time:.2f}s (Should be ~ {CONCURRENCY_LEVEL} x SingleReqTime)")

    generate_report()

def generate_report():
    report_content = f"""
# 📊 XTTS Service Benchmark Report
**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Environment:** Production Candidate

## 1. Key Performance Indicators (KPIs)
| Metric | Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **RTF (Real-Time Factor)** | `{results['rtf'][-1]:.4f}` | < 0.30 | {'✅ PASS' if results['rtf'][-1] < 0.3 else '⚠️ HIGH'} |
| **Streaming Latency (TTFB)** | `{results['latency_stream'][-1]:.0f} ms` | < 500 ms | {'✅ PASS' if results['latency_stream'][-1] < 500 else '⚠️ SLOW'} |
| **Queue Stability** | `{results['concurrency_success']}/{CONCURRENCY_LEVEL}` | 100% | {'✅ STABLE' if results['concurrency_success'] == CONCURRENCY_LEVEL else '❌ FAIL'} |

## 2. Analysis
- **RTF Analysis:** If RTF > 1.0, the system is slower than real-time (unusable for live).
- **Global Lock:** The system processed {CONCURRENCY_LEVEL} requests in parallel. If verified stable, the `threading.Lock()` in `engine.py` works correctly.

## 3. Configuration
- **Model:** XTTS v2
- **Device:** {requests.get(f"{BASE_URL}/health").json().get('device', 'Unknown')}
"""
    
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    console.print(f"\n[bold green]📄 Report generated: {OUTPUT_REPORT}[/bold green]")
    console.print(f"Please copy content of [bold]{OUTPUT_REPORT}[/bold] and report back to CTO.")

if __name__ == "__main__":
    run_benchmark()