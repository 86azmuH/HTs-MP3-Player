from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class LocalSyncStore:
    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or (Path(__file__).resolve().parent.parent / "controller_state.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_sync_meta (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_synced_version INTEGER NOT NULL DEFAULT 1,
                    dirty INTEGER NOT NULL DEFAULT 0,
                    pending_state_json TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                INSERT INTO controller_sync_meta (id, last_synced_version, dirty, pending_state_json)
                VALUES (1, 1, 0, NULL)
                ON CONFLICT(id) DO NOTHING
                """
            )
            conn.commit()

    def load_meta(self) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_synced_version, dirty, pending_state_json FROM controller_sync_meta WHERE id = 1"
            ).fetchone()
            if row is None:
                return {"last_synced_version": 1, "dirty": False, "pending_state": None}

            pending_state = None
            raw = row["pending_state_json"]
            if raw:
                try:
                    pending_state = json.loads(raw)
                except json.JSONDecodeError:
                    pending_state = None

            return {
                "last_synced_version": int(row["last_synced_version"]),
                "dirty": bool(row["dirty"]),
                "pending_state": pending_state,
            }

    def save_meta(self, *, last_synced_version: int, dirty: bool, pending_state: Optional[Dict[str, Any]]) -> None:
        pending_json = json.dumps(pending_state) if pending_state is not None else None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE controller_sync_meta
                SET last_synced_version = ?,
                    dirty = ?,
                    pending_state_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (int(last_synced_version), 1 if dirty else 0, pending_json),
            )
            conn.commit()
