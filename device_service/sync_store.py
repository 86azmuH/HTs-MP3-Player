from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class SyncStateStore:
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
                CREATE TABLE IF NOT EXISTS hub_sync_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    global_version INTEGER NOT NULL DEFAULT 1,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                INSERT INTO hub_sync_state (id, global_version, payload_json)
                VALUES (1, 1, '{}')
                ON CONFLICT(id) DO NOTHING
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS device_sync_checkpoint (
                    device_id TEXT PRIMARY KEY,
                    last_seen_version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def load_state(self) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT global_version, payload_json FROM hub_sync_state WHERE id = 1"
            ).fetchone()
            if row is None:
                return {"global_version": 1, "state": {}}

            payload_raw = row["payload_json"] or "{}"
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                payload = {}

            if not isinstance(payload, dict):
                payload = {}

            return {
                "global_version": int(row["global_version"]),
                "state": payload,
            }

    def save_state_if_version_matches(
        self,
        state: Dict[str, Any],
        expected_base_version: Optional[int],
    ) -> Tuple[bool, Dict[str, Any]]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT global_version FROM hub_sync_state WHERE id = 1"
            ).fetchone()
            current_version = int(row["global_version"]) if row is not None else 1

            if expected_base_version is not None and expected_base_version != current_version:
                conn.execute("ROLLBACK")
                current = self.load_state()
                return False, current

            next_version = current_version + 1
            payload_json = json.dumps(state)
            conn.execute(
                """
                UPDATE hub_sync_state
                SET global_version = ?, payload_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (next_version, payload_json),
            )
            conn.commit()

        return True, {"global_version": next_version, "state": state}

    def mark_device_seen(self, device_id: str, version: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_sync_checkpoint (device_id, last_seen_version, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(device_id) DO UPDATE SET
                    last_seen_version = excluded.last_seen_version,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (device_id, int(version)),
            )
            conn.commit()
