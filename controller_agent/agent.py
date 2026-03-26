from __future__ import annotations

import threading
from time import sleep, time
from typing import Any, Dict, Optional

from bootstrap import AppContext, build_context, switch_playlist
from controller_agent.local_store import LocalSyncStore
from controller_agent.sync_client import SyncClient, SyncClientError
from core.player import RepeatMode
from core.playlist import Playlist
from services.metadata_service import MetadataService


class OfflineControllerAgent:
    def __init__(
        self,
        *,
        device_id: str,
        hub_base_url: str,
        music_directory: str,
        sync_interval_seconds: float = 2.0,
    ):
        self.device_id = device_id
        self._ctx: AppContext = build_context(music_directory)
        self._sync_interval_seconds = max(0.5, sync_interval_seconds)

        self._sync_client = SyncClient(hub_base_url)
        self._store = LocalSyncStore()

        meta = self._store.load_meta()
        self._last_synced_version = int(meta["last_synced_version"])
        self._dirty = bool(meta["dirty"])
        self._pending_state: Optional[Dict[str, Any]] = meta.get("pending_state")

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._last_transition_signature = self._transition_signature(self._snapshot_state())

        if self._pending_state:
            self._apply_state(self._pending_state)

    @property
    def context(self) -> AppContext:
        return self._ctx

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.wait(self._sync_interval_seconds):
                with self._lock:
                    self._ctx.player.update()
                    self._sync_once_locked()

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.5)

        with self._lock:
            state = self._snapshot_state()
            if self._dirty:
                self._pending_state = state
            self._persist_meta_locked()

    def _persist_meta_locked(self) -> None:
        self._store.save_meta(
            last_synced_version=self._last_synced_version,
            dirty=self._dirty,
            pending_state=self._pending_state,
        )

    def _now_ms(self) -> int:
        return int(time() * 1000)

    def _snapshot_state(self) -> Dict[str, Any]:
        player = self._ctx.player
        queue_paths = [str(song.path) for song in player.playlist.songs]
        current_song_path = str(player.current_song.path) if player.current_song else None
        return {
            "current_song_path": current_song_path,
            "playlist_name": self._ctx.current_playlist_name,
            "playlist_index": int(player.playlist.current_index),
            "queue_paths": queue_paths,
            "status": player.state.name.lower(),
            "position_seconds": float(player.get_position() or 0.0),
            "volume": float(player.volume),
            "shuffle": bool(player.shuffle),
            "repeat_mode": player.repeat_mode.name,
            "updated_at_ms": self._now_ms(),
        }

    def _transition_signature(self, state: Dict[str, Any]) -> str:
        return "|".join(
            [
                str(state.get("current_song_path") or ""),
                str(state.get("playlist_name") or ""),
                str(state.get("playlist_index") or 0),
                str(state.get("status") or "stopped"),
                str(bool(state.get("shuffle", False))),
                str(state.get("repeat_mode") or "OFF"),
            ]
        )

    def _mark_dirty_locked(self) -> None:
        self._dirty = True
        self._pending_state = self._snapshot_state()
        self._last_transition_signature = self._transition_signature(self._pending_state)
        self._persist_meta_locked()

    def _load_queue_from_paths(self, queue_paths: list[str]) -> list:
        songs = []
        for song_path in queue_paths:
            try:
                songs.append(MetadataService.load_song(song_path))
            except Exception:
                continue
        return songs

    def _apply_state(self, state: Dict[str, Any]) -> None:
        playlist_name = state.get("playlist_name")
        if playlist_name and playlist_name in self._ctx.playlists_data:
            switch_playlist(self._ctx, playlist_name)
        else:
            queue_paths = state.get("queue_paths") or []
            if queue_paths:
                songs = self._load_queue_from_paths(queue_paths)
                if songs:
                    self._ctx.player.playlist = Playlist(songs)
                    self._ctx.current_playlist_name = "Synced Queue"

        songs = self._ctx.player.playlist.songs
        if songs:
            index = int(state.get("playlist_index", 0))
            current_song_path = state.get("current_song_path")
            if current_song_path:
                for i, song in enumerate(songs):
                    if str(song.path) == str(current_song_path):
                        index = i
                        break
            index = max(0, min(index, len(songs) - 1))
            self._ctx.player.playlist.set_index(index)

        self._ctx.player.set_volume(float(state.get("volume", self._ctx.player.volume)))
        self._ctx.player.shuffle = bool(state.get("shuffle", self._ctx.player.shuffle))

        repeat_mode_name = str(state.get("repeat_mode", self._ctx.player.repeat_mode.name))
        try:
            self._ctx.player.repeat_mode = RepeatMode[repeat_mode_name]
        except KeyError:
            pass

        position = float(state.get("position_seconds", 0.0))
        status = str(state.get("status", "stopped")).lower()

        if songs:
            try:
                if position > 0:
                    self._ctx.player.seek(position)

                if status == "playing":
                    self._ctx.player.play()
                elif status == "paused":
                    self._ctx.player.pause()
                else:
                    self._ctx.player.stop()
            except Exception:
                pass

    def _sync_once_locked(self) -> None:
        current_state = self._snapshot_state()
        current_signature = self._transition_signature(current_state)
        if current_signature != self._last_transition_signature:
            self._dirty = True
            self._pending_state = current_state
            self._last_transition_signature = current_signature
            self._persist_meta_locked()

        try:
            if self._dirty and self._pending_state is not None:
                push_resp = self._sync_client.push(
                    device_id=self.device_id,
                    base_version=self._last_synced_version,
                    state=self._pending_state,
                )

                if push_resp.get("applied"):
                    self._last_synced_version = int(push_resp.get("global_version", self._last_synced_version))
                    self._dirty = False
                    self._pending_state = None
                    self._persist_meta_locked()
                    return

                if push_resp.get("conflict"):
                    remote_state = push_resp.get("state") or {}
                    remote_version = int(push_resp.get("global_version", self._last_synced_version))
                    local_updated = int(self._pending_state.get("updated_at_ms") or 0)
                    remote_updated = int(remote_state.get("updated_at_ms") or 0)

                    if local_updated >= remote_updated:
                        retry = self._sync_client.push(
                            device_id=self.device_id,
                            base_version=remote_version,
                            state=self._pending_state,
                        )
                        if retry.get("applied"):
                            self._last_synced_version = int(retry.get("global_version", remote_version))
                            self._dirty = False
                            self._pending_state = None
                            self._persist_meta_locked()
                            return

                    self._apply_state(remote_state)
                    self._last_synced_version = remote_version
                    self._dirty = False
                    self._pending_state = None
                    self._persist_meta_locked()
                    return

            pull_resp = self._sync_client.pull(self.device_id, self._last_synced_version)
            if pull_resp.get("changed"):
                remote_state = pull_resp.get("state") or {}
                self._apply_state(remote_state)
                self._last_synced_version = int(pull_resp.get("global_version", self._last_synced_version))
                self._dirty = False
                self._pending_state = None
                self._last_transition_signature = self._transition_signature(self._snapshot_state())
                self._persist_meta_locked()
        except SyncClientError:
            return

    def play(self) -> None:
        with self._lock:
            self._ctx.player.play()
            self._mark_dirty_locked()

    def pause(self) -> None:
        with self._lock:
            self._ctx.player.pause()
            self._mark_dirty_locked()

    def stop(self) -> None:
        with self._lock:
            self._ctx.player.stop()
            self._mark_dirty_locked()

    def toggle_play_pause(self) -> None:
        with self._lock:
            self._ctx.player.toggle_play_pause()
            self._mark_dirty_locked()

    def next(self) -> None:
        with self._lock:
            self._ctx.player.next()
            self._mark_dirty_locked()

    def previous(self) -> None:
        with self._lock:
            self._ctx.player.previous()
            self._mark_dirty_locked()

    def seek(self, seconds: float) -> None:
        with self._lock:
            self._ctx.player.seek(seconds)
            self._mark_dirty_locked()

    def set_volume(self, volume: float) -> None:
        with self._lock:
            self._ctx.player.set_volume(volume)
            self._mark_dirty_locked()

    def toggle_shuffle(self) -> None:
        with self._lock:
            self._ctx.player.toggle_shuffle()
            self._mark_dirty_locked()

    def cycle_repeat_mode(self) -> None:
        with self._lock:
            self._ctx.player.cycle_repeat_mode()
            self._mark_dirty_locked()

    def select_index(self, index: int) -> None:
        with self._lock:
            self._ctx.player.playlist.set_index(index)
            self._mark_dirty_locked()


def run_forever(agent: OfflineControllerAgent) -> None:
    agent.start()
    try:
        while True:
            sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        agent.shutdown()
