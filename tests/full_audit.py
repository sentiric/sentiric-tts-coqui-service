import time
import uuid
import requests
import json
import statistics
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# --- CONFIG ---
API_URL = "http://localhost:14030"
API_TTS = f"{API_URL}/api/tts"
OUTPUT_DIR = "/tmp/sentiric-audit"
os.makedirs(OUTPUT_DIR, exist_ok=True)

console = Console()

class SentiricAuditor:
    def __init__(self):
        self.session = requests.Session()

    def _generate_unique_text(self, length="short"):
        uid = uuid.uuid4().hex[:8]
        if length == "short": return f"Hello system {uid}."
        return f"This is a longer sentence to measure stability {uid}."

    def check_health(self):
        try:
            start = time.perf_counter()
            r = self.session.get(f"{API_URL}/health", timeout=2)
            lat = (time.perf_counter() - start) * 1000
            if r.status_code == 200:
                data = r.json()
                console.print(f"[green]✅ System Online[/green] | Ping: {lat:.1f}ms | Device: {data.get('device')}")
                return True
            console.print(f"[red]❌ Health Check Failed: {r.status_code}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ System Unreachable: {e}[/red]")
            return False

    def measure_inference_latency(self, iterations=3):
        console.print(Panel("[bold yellow]🧪 TEST 1: Pure Inference Latency[/bold yellow]"))
        table = Table(title="Metrics")
        table.add_column("Iter"); table.add_column("Total (ms)"); table.add_column("RTF")
        
        latencies = []
        for i in range(iterations):
            text = self._generate_unique_text("medium")
            start = time.perf_counter()
            r = self.session.post(API_TTS, json={"text": text, "language": "en", "stream": False})
            end = time.perf_counter()
            
            if r.status_code == 200:
                total_ms = (end - start) * 1000
                audio_len = len(r.content) / (24000 * 2)
                rtf = (end - start) / audio_len if audio_len > 0 else 0
                table.add_row(str(i+1), f"{total_ms:.0f}", f"{rtf:.4f}")
                latencies.append(total_ms)
            else:
                table.add_row(str(i+1), "ERR", "ERR")

        console.print(table)
        if latencies:
            avg = statistics.mean(latencies)
            console.print(f"ℹ️  Average: {avg:.0f} ms")

    def run_all(self):
        console.rule("[bold]SENTIRIC AUDIT[/bold]")
        if self.check_health():
            self.measure_inference_latency()
        console.rule("[bold]COMPLETE[/bold]")

if __name__ == "__main__":
    auditor = SentiricAuditor()
    auditor.run_all()