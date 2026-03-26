from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from threading import Event, Lock, Thread
from typing import Optional

from fastapi import HTTPException

from bootstrap import AppContext, build_context, save_state, switch_playlist
from core.player import RepeatMode
from device_service.state_store import DeviceStateStore


@dataclass
class VersionState:
    state_version: int = 1
    queue_version: int = 1


class PlaybackController:
    _CHECKPOINT_INTERVAL_SECONDS = 5.0

    def __init__(self, music_directory: str):
        self._music_directory = music_directory
        self._ctx: AppContext = build_context(music_directory)
        self._versions = VersionState()
        self._lock = Lock()
        self._stop_event = Event()
        self._update_thread: Optional[Thread] = None
        self._state_store = DeviceStateStore()
        self._last_checkpoint_at = 0.0

        self._restore_from_snapshot()

    @property
    def context(self) -> AppContext:
        return self._ctx

    @property
    def versions(self) -> VersionState:
        return self._versions

    def start(self) -> None:
        if self._update_thread is not None and self._update_thread.is_alive():
            return

        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.wait(0.5):
                with self._lock:
                    before_index = self._ctx.player.playlist.current_index
                    before_state = self._ctx.player.state
                    self._ctx.player.update()
                    after_index = self._ctx.player.playlist.current_index
                    after_state = self._ctx.player.state

                    if after_index != before_index:
                        self._versions.queue_version += 1
                        self._versions.state_version += 1
                    elif after_state != before_state:
                        self._versions.state_version += 1

                    self._checkpoint_if_due_locked()

        self._update_thread = Thread(target=_loop, daemon=True)
        self._update_thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._update_thread is not None:
            self._update_thread.join(timeout=1.5)

        with self._lock:
            self._persist_snapshot_locked()
            save_state(self._ctx)

    def _mark_state_changed(self) -> None:
        self._versions.state_version += 1
        self._persist_snapshot_locked()

    def _mark_queue_changed(self) -> None:
        self._versions.queue_version += 1
        self._versions.state_version += 1
        self._persist_snapshot_locked()

    def _restore_from_snapshot(self) -> None:
        snapshot = self._state_store.load_snapshot()
        if snapshot is None:
            return

        playlist_name = snapshot.get("playlist_name")
        if playlist_name:
            switch_playlist(self._ctx, playlist_name)

        index = int(snapshot.get("playlist_index", 0))
        songs = self._ctx.player.playlist.songs
        if songs:
            index = max(0, min(index, len(songs) - 1))
            self._ctx.player.playlist.set_index(index)

        self._ctx.player.set_volume(float(snapshot.get("volume", self._ctx.player.volume)))
        self._ctx.player.shuffle = bool(snapshot.get("shuffle", self._ctx.player.shuffle))

        repeat_mode = snapshot.get("repeat_mode")
        try:
            if repeat_mode:
                self._ctx.player.repeat_mode = RepeatMode[repeat_mode]
        except KeyError:
            pass

        position_seconds = float(snapshot.get("position_seconds", 0.0))
        if position_seconds > 0:
            try:
                self._ctx.player.seek(position_seconds)
            except Exception:
                pass

        self._versions.state_version = max(1, int(snapshot.get("state_version", 1)))
        self._versions.queue_version = max(1, int(snapshot.get("queue_version", 1)))

    def _build_snapshot_locked(self) -> dict:
        player = self._ctx.player
        return {
            "playlist_name": self._ctx.current_playlist_name,
            "playlist_index": player.playlist.current_index,
            "volume": player.volume,
            "shuffle": player.shuffle,
            "repeat_mode": player.repeat_mode.name,
            "position_seconds": player.get_position() or 0.0,
            "status": player.state.name.lower(),
            "state_version": self._versions.state_version,
            "queue_version": self._versions.queue_version,
        }

    def _persist_snapshot_locked(self) -> None:
        self._state_store.save_snapshot(self._build_snapshot_locked())
        self._last_checkpoint_at = monotonic()

    def _checkpoint_if_due_locked(self) -> None:
        now = monotonic()
        if (now - self._last_checkpoint_at) < self._CHECKPOINT_INTERVAL_SECONDS:
            return
        self._persist_snapshot_locked()

    def play(self) -> None:
        with self._lock:
            self._ctx.player.play()
            self._mark_state_changed()

    def pause(self) -> None:
        with self._lock:
            self._ctx.player.pause()
            self._mark_state_changed()

    def stop(self) -> None:
        with self._lock:
            self._ctx.player.stop()
            self._mark_state_changed()

    def toggle_play_pause(self) -> None:
        with self._lock:
            self._ctx.player.toggle_play_pause()
            self._mark_state_changed()

    def next(self) -> None:
        with self._lock:
            self._ctx.player.next()
            self._mark_queue_changed()

    def previous(self) -> None:
        with self._lock:
            self._ctx.player.previous()
            self._mark_queue_changed()

    def seek(self, position_seconds: float) -> None:
        with self._lock:
            self._ctx.player.seek(position_seconds)
            self._mark_state_changed()

    def set_volume(self, volume: float) -> None:
        with self._lock:
            self._ctx.player.set_volume(volume)
            self._mark_state_changed()

    def toggle_shuffle(self) -> None:
        with self._lock:
            self._ctx.player.toggle_shuffle()
            self._mark_state_changed()

    def cycle_repeat_mode(self) -> None:
        with self._lock:
            self._ctx.player.cycle_repeat_mode()
            self._mark_state_changed()

    def _check_base_queue_version(self, base_version: Optional[int]) -> None:
        if base_version is None:
            return
        if base_version != self._versions.queue_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Queue version conflict",
                    "expected_queue_version": self._versions.queue_version,
                    "provided_base_version": base_version,
                },
            )

    def select_index(self, index: int, base_version: Optional[int] = None) -> None:
        with self._lock:
            self._check_base_queue_version(base_version)
            self._ctx.player.playlist.set_index(index)
            self._mark_queue_changed()

    def play_index(self, index: int, base_version: Optional[int] = None) -> None:
        with self._lock:
            self._check_base_queue_version(base_version)
            self._ctx.player.playlist.set_index(index)
            self._ctx.player.stop()
            self._ctx.player.play()
            self._mark_queue_changed()

    def use_playlist(self, name: str, base_version: Optional[int] = None) -> None:
        with self._lock:
            self._check_base_queue_version(base_version)
            ok = switch_playlist(self._ctx, name)
            if not ok:
                raise HTTPException(status_code=404, detail=f"Playlist '{name}' not found")

            try:
                self._ctx.player.load_current_song()
            except Exception:
                pass

            self._ctx.player.stop()

            self._mark_queue_changed()

    def reload_library(self) -> int:
        with self._lock:
            try:
                self._ctx.player.stop()
            except Exception:
                pass

            audio_adapter = getattr(self._ctx.player, "_audio_adapter", None)
            self._ctx = build_context(self._music_directory, audio_adapter=audio_adapter)
            self._mark_queue_changed()
            save_state(self._ctx)
            return len(self._ctx.scanned_songs)
