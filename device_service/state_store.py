from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class DeviceStateStore:
    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or (Path(__file__).resolve().parent.parent / "device_state.db")
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
                CREATE TABLE IF NOT EXISTS device_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    playlist_name TEXT,
                    playlist_index INTEGER NOT NULL DEFAULT 0,
                    volume REAL NOT NULL DEFAULT 1.0,
                    shuffle INTEGER NOT NULL DEFAULT 0,
                    repeat_mode TEXT NOT NULL DEFAULT 'OFF',
                    position_seconds REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'stopped',
                    state_version INTEGER NOT NULL DEFAULT 1,
                    queue_version INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def load_snapshot(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM device_state WHERE id = 1").fetchone()
            if row is None:
                return None

            return {
                "playlist_name": row["playlist_name"],
                "playlist_index": int(row["playlist_index"]),
                "volume": float(row["volume"]),
                "shuffle": bool(row["shuffle"]),
                "repeat_mode": row["repeat_mode"],
                "position_seconds": float(row["position_seconds"]),
                "status": row["status"],
                "state_version": int(row["state_version"]),
                "queue_version": int(row["queue_version"]),
                "updated_at": row["updated_at"],
            }

    def save_snapshot(self, snapshot: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_state (
                    id,
                    playlist_name,
                    playlist_index,
                    volume,
                    shuffle,
                    repeat_mode,
                    position_seconds,
                    status,
                    state_version,
                    queue_version,
                    updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    playlist_name = excluded.playlist_name,
                    playlist_index = excluded.playlist_index,
                    volume = excluded.volume,
                    shuffle = excluded.shuffle,
                    repeat_mode = excluded.repeat_mode,
                    position_seconds = excluded.position_seconds,
                    status = excluded.status,
                    state_version = excluded.state_version,
                    queue_version = excluded.queue_version,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    snapshot.get("playlist_name"),
                    int(snapshot.get("playlist_index", 0)),
                    float(snapshot.get("volume", 1.0)),
                    1 if bool(snapshot.get("shuffle", False)) else 0,
                    str(snapshot.get("repeat_mode", "OFF")),
                    float(snapshot.get("position_seconds", 0.0)),
                    str(snapshot.get("status", "stopped")),
                    int(snapshot.get("state_version", 1)),
                    int(snapshot.get("queue_version", 1)),
                ),
            )
            conn.commit()
