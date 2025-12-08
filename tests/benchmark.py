import time
import requests
import json
import threading
import concurrent.futures
import io
import soundfile as sf
import statistics
import os
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from datetime import datetime

# --- CONFIGURATION ---
BASE_URL = "http://localhost:14030"
API_URL = f"{BASE_URL}/api/tts"
# DÜZELTME: /tmp dizinini kullan
OUTPUT_DIR = "/tmp/sentiric-tts-tests"
OUTPUT_REPORT = os.path.join(OUTPUT_DIR, "benchmark_report.md")

TEST_TEXT = "Sentiric XTTS servisi, yapay zeka tabanlı ses sentezleme teknolojilerinde yüksek performans ve düşük gecikme süresi hedefler. Bu bir performans testidir."
TEST_SPEAKER = "F_TR_Kurumsal_Ece"
CONCURRENCY_LEVEL = 5

console = Console()
results = {
    "latency_stream": [], "latency_non_stream": [], "rtf": [],
    "errors": 0, "concurrency_success": 0
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
    payload = {
        "text": TEST_TEXT, "language": "tr", "speaker_idx": TEST_SPEAKER,
        "stream": False, "split_sentences": False
    }
    start_time = time.perf_counter()
    response = requests.post(API_URL, json=payload)
    end_time = time.perf_counter()
    
    if response.status_code == 200 and len(response.content) > 1000:
        process_time = end_time - start_time
        audio_data = io.BytesIO(response.content)
        data, samplerate = sf.read(audio_data)
        audio_duration = len(data) / samplerate
        rtf = process_time / audio_duration
        results["rtf"].append(rtf)
        results["latency_non_stream"].append(process_time)
        return process_time, audio_duration, rtf
    else:
        results["errors"] += 1
        console.print(f"[red]RTF measurement failed! Status: {response.status_code}, Size: {len(response.content)} bytes[/red]")
        if response.status_code == 500: console.print(f"   [bold red]Server Error: {response.text}[/bold red]")
        return None, None, None

def measure_streaming_latency():
    payload = { "text": "Merhaba", "language": "tr", "speaker_idx": TEST_SPEAKER, "stream": True }
    start_time = time.perf_counter()
    try:
        with requests.post(API_URL, json=payload, stream=True, timeout=10) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    latency = (time.perf_counter() - start_time) * 1000
                    results["latency_stream"].append(latency)
                    break 
    except Exception as e:
        console.print(f"[red]Stream Error: {e}[/red]")
        results["errors"] += 1

def concurrency_task(id):
    try:
        payload = { "text": f"Thread {id}", "language": "tr", "speaker_idx": TEST_SPEAKER }
        r = requests.post(API_URL, json=payload, timeout=30)
        return r.status_code == 200 and len(r.content) > 0
    except: return False

def run_benchmark():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not check_health(): return

    console.print("\n[bold cyan]🚀 SENTIRIC XTTS PERFORMANCE BENCHMARK[/bold cyan]")
    with console.status("[yellow]🔥 Warming up model...[/yellow]"): measure_rtf()
    console.print("\n[bold]1. Single Request Performance[/bold]")
    proc_time, audio_dur, rtf = measure_rtf()
    if rtf: console.print(f"   [green]OK[/green] | RTF: {rtf:.4f}")
    console.print("\n[bold]2. Streaming Latency (TTFB)[/bold]")
    measure_streaming_latency()
    if results["latency_stream"]: console.print(f"   [green]OK[/green] | TTFB: {results['latency_stream'][-1]:.0f}ms")
    console.print(f"\n[bold]3. Concurrency Stress Test[/bold]")
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY_LEVEL) as executor:
        futures = [executor.submit(concurrency_task, i) for i in range(CONCURRENCY_LEVEL)]
        results["concurrency_success"] = sum(f.result() for f in concurrent.futures.as_completed(futures))
    console.print(f"   [green]OK[/green] | Success Rate: {results['concurrency_success']}/{CONCURRENCY_LEVEL}")
    generate_report()

def generate_report():
    rtf_val = f"{results['rtf'][-1]:.4f}" if results['rtf'] else "FAIL"
    lat_val = f"{results['latency_stream'][-1]:.0f} ms" if results['latency_stream'] else "FAIL"
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f: f.write(f"# BENCHMARK\nRTF: {rtf_val}\nLATENCY: {lat_val}\n")
    console.print(f"\n[bold green]📄 Report generated: {OUTPUT_REPORT}[/bold green]")

if __name__ == "__main__":
    run_benchmark()