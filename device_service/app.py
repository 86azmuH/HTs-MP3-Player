from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from bootstrap import resolve_directory
from core.player import PlaybackState
from device_service.controller import PlaybackController
from device_service.models import (
    PlayQueueItemRequest,
    LibraryReconcileRequest,
    LibraryReconcileResponse,
    PlaybackActionResponse,
    CreatePlaylistRequest,
    DeletePlaylistRequest,
    LibraryUploadResponse,
    PlaylistActionResponse,
    PlaylistListResponse,
    PlaylistSongRequest,
    QueueItem,
    QueueResponse,
    SeekRequest,
    SelectQueueItemRequest,
    StateResponse,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncState,
    UsePlaylistRequest,
    VolumeRequest,
)
from device_service.sync_store import SyncStateStore


def _status_name(state: PlaybackState) -> str:
    return state.name.lower()


def _sanitize_device_id(device_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", device_id.strip())
    return cleaned[:100] or "device"


def create_app(music_directory: str) -> FastAPI:
    app = FastAPI(title="MP3 Player Device Service", version="0.1.0")
    controller = PlaybackController(music_directory)
    sync_store = SyncStateStore()
    web_dir = Path(__file__).resolve().parent / "web"
    media_dir = Path(music_directory)

    if web_dir.exists():
        app.mount("/controller/static", StaticFiles(directory=str(web_dir)), name="controller-static")

    @app.on_event("startup")
    def _on_startup() -> None:
        controller.start()

    @app.on_event("shutdown")
    def _on_shutdown() -> None:
        controller.shutdown()

    @app.get("/v1/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/controller")

    @app.get("/controller")
    def controller_ui() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    @app.get("/v1/state", response_model=StateResponse)
    def get_state() -> StateResponse:
        ctx = controller.context
        player = ctx.player
        song = player.current_song

        return StateResponse(
            status=_status_name(player.state),
            current_song_title=song.title if song else None,
            current_song_artist=song.artist if song else None,
            current_song_album=song.album if song else None,
            current_song_path=str(song.path) if song else None,
            playlist_name=ctx.current_playlist_name,
            playlist_index=player.playlist.current_index,
            playlist_length=player.playlist.length,
            volume=player.volume,
            shuffle=player.shuffle,
            repeat_mode=player.repeat_mode.name,
            position_seconds=player.get_position() or 0.0,
            length_seconds=player.get_length(),
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
        )

    @app.get("/v1/queue", response_model=QueueResponse)
    def get_queue() -> QueueResponse:
        ctx = controller.context
        items = [
            QueueItem(
                index=index,
                title=song.title,
                artist=song.artist,
                album=song.album,
                duration=song.duration,
                path=str(song.path),
                is_current=(index == ctx.player.playlist.current_index),
            )
            for index, song in enumerate(ctx.player.playlist.songs)
        ]

        return QueueResponse(
            queue_version=controller.versions.queue_version,
            playlist_name=ctx.current_playlist_name,
            items=items,
        )

    @app.post("/v1/playback/play", response_model=PlaybackActionResponse)
    def play() -> PlaybackActionResponse:
        controller.play()
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message="Playback started",
        )

    @app.post("/v1/playback/pause", response_model=PlaybackActionResponse)
    def pause() -> PlaybackActionResponse:
        controller.pause()
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message="Playback paused",
        )

    @app.post("/v1/playback/stop", response_model=PlaybackActionResponse)
    def stop() -> PlaybackActionResponse:
        controller.stop()
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message="Playback stopped",
        )

    @app.post("/v1/playback/toggle", response_model=PlaybackActionResponse)
    def toggle_play_pause() -> PlaybackActionResponse:
        controller.toggle_play_pause()
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message="Playback toggled",
        )

    @app.post("/v1/playback/next", response_model=PlaybackActionResponse)
    def next_track() -> PlaybackActionResponse:
        controller.next()
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message="Advanced to next track",
        )

    @app.post("/v1/playback/prev", response_model=PlaybackActionResponse)
    def previous_track() -> PlaybackActionResponse:
        controller.previous()
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message="Moved to previous track",
        )

    @app.post("/v1/playback/seek", response_model=PlaybackActionResponse)
    def seek(req: SeekRequest) -> PlaybackActionResponse:
        controller.seek(req.position_seconds)
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message=f"Seeked to {req.position_seconds:.2f}s",
        )

    @app.post("/v1/playback/volume", response_model=PlaybackActionResponse)
    def set_volume(req: VolumeRequest) -> PlaybackActionResponse:
        controller.set_volume(req.volume)
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message=f"Volume set to {req.volume:.2f}",
        )

    @app.post("/v1/playback/shuffle/toggle", response_model=PlaybackActionResponse)
    def toggle_shuffle() -> PlaybackActionResponse:
        controller.toggle_shuffle()
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message="Shuffle toggled",
        )

    @app.post("/v1/playback/repeat/cycle", response_model=PlaybackActionResponse)
    def cycle_repeat_mode() -> PlaybackActionResponse:
        controller.cycle_repeat_mode()
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message="Repeat mode cycled",
        )

    @app.post("/v1/queue/select", response_model=PlaybackActionResponse)
    def select_queue_item(req: SelectQueueItemRequest) -> PlaybackActionResponse:
        controller.select_index(req.index, base_version=req.base_version)
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message=f"Selected queue index {req.index}",
        )

    @app.post("/v1/queue/play", response_model=PlaybackActionResponse)
    def play_queue_item(req: PlayQueueItemRequest) -> PlaybackActionResponse:
        controller.play_index(req.index, base_version=req.base_version)
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message=f"Playing queue index {req.index}",
        )

    @app.get("/v1/library")
    def get_library():
        ctx = controller.context
        return {
            "songs": [
                {"path": str(s.path), "title": s.title, "artist": s.artist}
                for s in ctx.scanned_songs
            ]
        }

    @app.get("/v1/playlists", response_model=PlaylistListResponse)
    def get_playlists() -> PlaylistListResponse:
        ctx = controller.context
        return PlaylistListResponse(
            names=ctx.playlist_service.get_playlist_names(ctx.playlists_data),
            current_playlist_name=ctx.current_playlist_name,
            queue_version=controller.versions.queue_version,
        )

    @app.get("/v1/sync/pull", response_model=SyncPullResponse)
    def sync_pull(device_id: str, since_version: int | None = None) -> SyncPullResponse:
        current = sync_store.load_state()
        global_version = int(current["global_version"])
        sync_store.mark_device_seen(device_id, global_version)

        changed = since_version is None or int(since_version) < global_version
        return SyncPullResponse(
            changed=changed,
            global_version=global_version,
            state=SyncState(**current["state"]),
        )

    @app.post("/v1/sync/push", response_model=SyncPushResponse)
    def sync_push(req: SyncPushRequest) -> SyncPushResponse:
        applied, current = sync_store.save_state_if_version_matches(
            state=req.state.dict(),
            expected_base_version=req.base_version,
        )
        global_version = int(current["global_version"])
        sync_store.mark_device_seen(req.device_id, global_version)

        if not applied:
            return SyncPushResponse(
                applied=False,
                conflict=True,
                global_version=global_version,
                state=SyncState(**current["state"]),
                message="Sync conflict: base_version does not match current global version",
            )

        return SyncPushResponse(
            applied=True,
            conflict=False,
            global_version=global_version,
            state=SyncState(**current["state"]),
            message="Sync state applied",
        )

    @app.post("/v1/playlists/use", response_model=PlaybackActionResponse)
    def use_playlist(req: UsePlaylistRequest) -> PlaybackActionResponse:
        controller.use_playlist(req.name, base_version=req.base_version)
        return PlaybackActionResponse(
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message=f"Switched to playlist '{req.name}'",
        )

    def _playlist_action_response(message: str) -> PlaylistActionResponse:
        ctx = controller.context
        return PlaylistActionResponse(
            names=ctx.playlist_service.get_playlist_names(ctx.playlists_data),
            current_playlist_name=ctx.current_playlist_name,
            queue_version=controller.versions.queue_version,
            message=message,
        )

    @app.post("/v1/playlists/create", response_model=PlaylistActionResponse)
    def create_playlist(req: CreatePlaylistRequest) -> PlaylistActionResponse:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Playlist name cannot be empty")
        ctx = controller.context
        with controller._lock:
            if name in ctx.playlists_data:
                raise HTTPException(status_code=409, detail=f"Playlist '{name}' already exists")
            ctx.playlists_data[name] = []
            ctx.playlist_service.save(ctx.playlists_data)
        return _playlist_action_response(f"Created playlist '{name}'")

    @app.post("/v1/playlists/delete", response_model=PlaylistActionResponse)
    def delete_playlist(req: DeletePlaylistRequest) -> PlaylistActionResponse:
        if req.name == "All songs":
            raise HTTPException(status_code=400, detail="Cannot delete 'All songs'")
        ctx = controller.context
        with controller._lock:
            if req.name not in ctx.playlists_data:
                raise HTTPException(status_code=404, detail=f"Playlist '{req.name}' not found")
            del ctx.playlists_data[req.name]
            ctx.playlist_service.save(ctx.playlists_data)
            if ctx.current_playlist_name == req.name:
                from bootstrap import switch_playlist
                switch_playlist(ctx, "All songs")
        return _playlist_action_response(f"Deleted playlist '{req.name}'")

    @app.post("/v1/playlists/add-song", response_model=PlaylistActionResponse)
    def add_song_to_playlist(req: PlaylistSongRequest) -> PlaylistActionResponse:
        ctx = controller.context
        with controller._lock:
            if req.playlist_name not in ctx.playlists_data:
                raise HTTPException(status_code=404, detail=f"Playlist '{req.playlist_name}' not found")
            if req.playlist_name == "All songs":
                raise HTTPException(status_code=400, detail="Cannot manually edit 'All songs'")
            if req.song_path not in ctx.playlists_data[req.playlist_name]:
                ctx.playlists_data[req.playlist_name].append(req.song_path)
                ctx.playlist_service.save(ctx.playlists_data)
        return _playlist_action_response(f"Added song to '{req.playlist_name}'")

    @app.post("/v1/playlists/remove-song", response_model=PlaylistActionResponse)
    def remove_song_from_playlist(req: PlaylistSongRequest) -> PlaylistActionResponse:
        ctx = controller.context
        with controller._lock:
            if req.playlist_name not in ctx.playlists_data:
                raise HTTPException(status_code=404, detail=f"Playlist '{req.playlist_name}' not found")
            if req.playlist_name == "All songs":
                raise HTTPException(status_code=400, detail="Cannot manually edit 'All songs'")
            tracks = ctx.playlists_data[req.playlist_name]
            ctx.playlists_data[req.playlist_name] = [p for p in tracks if p != req.song_path]
            ctx.playlist_service.save(ctx.playlists_data)
        return _playlist_action_response(f"Removed song from '{req.playlist_name}'")

    @app.post("/v1/library/upload", response_model=LibraryUploadResponse)
    def upload_library(
        files: list[UploadFile] = File(...),
        device_id: str | None = Form(default=None),
    ) -> LibraryUploadResponse:
        target_dir = media_dir
        if device_id:
            safe_device_id = _sanitize_device_id(device_id)
            target_dir = media_dir / "controller_uploads" / safe_device_id

        target_dir.mkdir(parents=True, exist_ok=True)
        saved_files: list[str] = []
        skipped_files: list[str] = []

        for upload in files:
            raw_name = upload.filename or ""
            safe_name = Path(raw_name).name
            if not safe_name or not safe_name.lower().endswith(".mp3"):
                skipped_files.append(raw_name or "(unnamed)")
                continue

            target = target_dir / safe_name
            base_stem = target.stem
            suffix = target.suffix
            sequence = 1
            while target.exists():
                target = target_dir / f"{base_stem}_{sequence}{suffix}"
                sequence += 1

            with target.open("wb") as out_file:
                shutil.copyfileobj(upload.file, out_file)
            saved_files.append(target.name)

        if saved_files:
            controller.reload_library()

        message = (
            f"Uploaded {len(saved_files)} file(s)"
            if saved_files
            else "No MP3 files uploaded"
        )
        if skipped_files:
            message = f"{message}; skipped {len(skipped_files)} non-mp3 file(s)"

        return LibraryUploadResponse(
            uploaded_count=len(saved_files),
            saved_files=saved_files,
            skipped_files=skipped_files,
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message=message,
        )

    @app.post("/v1/library/reconcile", response_model=LibraryReconcileResponse)
    def reconcile_library(req: LibraryReconcileRequest) -> LibraryReconcileResponse:
        safe_device_id = _sanitize_device_id(req.device_id)
        device_dir = media_dir / "controller_uploads" / safe_device_id
        if not device_dir.exists():
            device_dir.mkdir(parents=True, exist_ok=True)

        desired = {
            Path(name).name
            for name in req.files
            if name and Path(name).name.lower().endswith(".mp3")
        }

        removed_files: list[str] = []
        for existing in device_dir.glob("*.mp3"):
            if existing.name not in desired:
                existing.unlink(missing_ok=True)
                removed_files.append(existing.name)

        if removed_files:
            controller.reload_library()

        message = (
            f"Removed {len(removed_files)} file(s)"
            if removed_files
            else "No files removed"
        )

        return LibraryReconcileResponse(
            removed_count=len(removed_files),
            removed_files=removed_files,
            state_version=controller.versions.state_version,
            queue_version=controller.versions.queue_version,
            message=message,
        )

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MP3 Player device service")
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Music directory (defaults to media/ then cwd fallback)",
    )
    return parser.parse_args()


def build_app_from_cli_args() -> FastAPI:
    args = parse_args()
    directory = resolve_directory(args.directory)
    return create_app(str(Path(directory)))
