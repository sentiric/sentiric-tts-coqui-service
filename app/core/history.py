import sqlite3
import json
import os
import uuid
import time
import glob
from datetime import datetime
from typing import List, Dict, Optional

class HistoryManager:
    def __init__(self, db_path: str = "/app/history/history.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                text TEXT,
                speaker TEXT,
                mode TEXT,
                date TEXT,
                timestamp REAL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON history(timestamp DESC);")
        conn.commit()
        conn.close()

    def add_entry(self, filename: str, text: str, speaker: str, mode: str):
        entry_id = str(uuid.uuid4())
        preview_text = text[:50] + "..." if len(text) > 50 else text
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        timestamp = time.time()

        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO history (id, filename, text, speaker, mode, date, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (entry_id, filename, preview_text, speaker, mode, date_str, timestamp))
            
            # Otomatik Temizlik: Son 50 kaydı tut
            conn.execute("""
                DELETE FROM history WHERE id NOT IN (
                    SELECT id FROM history ORDER BY timestamp DESC LIMIT 50
                )
            """)
            conn.commit()
            return {
                "id": entry_id, "filename": filename, "text": preview_text,
                "speaker": speaker, "mode": mode, "date": date_str, "timestamp": timestamp
            }
        except Exception as e:
            print(f"DB Error: {e}")
            return None
        finally:
            conn.close()

    def get_all(self) -> List[Dict]:
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT * FROM history ORDER BY timestamp DESC LIMIT 50")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
            
    def delete_entry(self, filename: str):
        """Tekil bir kaydı DB'den siler"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM history WHERE filename = ?", (filename,))
            conn.commit()
        finally:
            conn.close()

    def clear_all(self):
        """Tüm tabloyu temizler"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM history")
            conn.commit()
        finally:
            conn.close()

history_manager = HistoryManager()