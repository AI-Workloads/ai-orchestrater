import json
import sqlite3
from pathlib import Path
from .models import Orchestration

DB = Path(__file__).resolve().parents[1] / "orchestrator.db"

class StateStore:
    def __init__(self):
        self.db = sqlite3.connect(DB, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS orchestrations (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self.db.commit()

    def save(self, item: Orchestration):
        self.db.execute("INSERT OR REPLACE INTO orchestrations VALUES (?, ?)", (item.id, item.model_dump_json()))
        self.db.commit()

    def get(self, oid: str) -> Orchestration | None:
        row = self.db.execute("SELECT data FROM orchestrations WHERE id=?", (oid,)).fetchone()
        return Orchestration.model_validate_json(row[0]) if row else None
