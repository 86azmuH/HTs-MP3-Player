"""Shared application bootstrap for the MP3 player.

Both the Tkinter GUI (main.py) and the headless CLI (ui/cli.py) call
build_context() to get a fully initialised AppContext.  No frontend code
lives here — only core/service wiring and persistence handling.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from core.player import Player, RepeatMode
from core.playlist import Playlist
from core.song import Song
from services.audio_service import AudioAdapter, DummyAudioAdapter, PygameAudioAdapter
from services.file_service import FileService
from services.metadata_service import MetadataService
from services.playlist_service import PlaylistService
from services.settings_service import SettingsService


# ---------------------------------------------------------------------------
# Runtime context
# ---------------------------------------------------------------------------

@dataclass
class AppContext:
    """Carries every runtime object both frontends need."""
    player: Player
    settings_service: SettingsService
    playlist_service: PlaylistService
    playlists_data: Dict[str, List[str]]
    current_playlist_name: str
    scanned_songs: List[Song]


# ---------------------------------------------------------------------------
# Directory resolution
# ---------------------------------------------------------------------------

def resolve_directory(explicit_path: Optional[str] = None) -> Path:
    """Resolve the music directory with PyInstaller-frozen and cwd fallback.

    Priority:
    1. explicit_path if given
    2. <project_root>/media/
    3. cwd() if the above does not exist
    """
    if getattr(sys, "frozen", False):
        app_base = Path(sys._MEIPASS)
    else:
        app_base = Path(__file__).parent

    default_media = app_base / "media"
    directory = Path(explicit_path) if explicit_path else default_media

    if not directory.exists() or not directory.is_dir():
        fallback = Path.cwd()
        if fallback.exists() and fallback.is_dir():
            directory = fallback
        else:
            raise FileNotFoundError(f"Directory does not exist: {directory}")

    return directory


# ---------------------------------------------------------------------------
# Audio adapter factory
# ---------------------------------------------------------------------------

def create_audio_adapter() -> AudioAdapter:
    """Return PygameAudioAdapter if available, else DummyAudioAdapter."""
    try:
        return PygameAudioAdapter()
    except Exception as exc:
        print(f"WARNING: pygame audio adapter unavailable: {exc}. Using dummy adapter.")
        return DummyAudioAdapter()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_playlist_songs(
    playlists_data: Dict[str, List[str]], name: str
) -> List[Song]:
    """Load Song objects for a named playlist, silently skipping missing files."""
    songs: List[Song] = []
    for p in playlists_data.get(name, []):
        try:
            songs.append(MetadataService.load_song(p))
        except FileNotFoundError:
            continue
    return songs


# ---------------------------------------------------------------------------
# Public bootstrap
# ---------------------------------------------------------------------------

def build_context(
    directory: str,
    audio_adapter: Optional[AudioAdapter] = None,
) -> AppContext:
    """Scan songs, load persistence, and return a ready-to-use AppContext.

    Both the GUI and CLI call this.  Pass audio_adapter to inject a specific
    backend (useful in tests).
    """
    songs = FileService.scan_mp3_directory(directory)
    if not songs:
        print(
            "WARNING: No MP3 files found in directory; "
            "starting with empty library."
        )

    settings_service = SettingsService()
    saved = settings_service.load()

    playlist_service = PlaylistService()
    playlists_data = playlist_service.load()

    if playlist_service.clean_missing_files(playlists_data):
        playlist_service.save(playlists_data)

    # "All songs" is always rebuilt from the current scan — never user-curated.
    all_song_paths = [str(s.path) for s in songs]
    playlists_data.setdefault("All songs", all_song_paths)
    playlists_data["All songs"] = all_song_paths

    playlist_name = saved.get("playlist_name", "All songs")
    if playlist_name not in playlists_data:
        playlist_name = "All songs"

    selected_songs = _load_playlist_songs(playlists_data, playlist_name)
    if not selected_songs:
        selected_songs = list(songs)

    playlist = Playlist(selected_songs)
    last_index = saved.get("playlist_index", 0)
    if isinstance(last_index, int) and 0 <= last_index < len(selected_songs):
        playlist.set_index(last_index)

    if audio_adapter is None:
        audio_adapter = create_audio_adapter()

    player = Player(playlist, audio_adapter)

    try:
        player.load_current_song()
    except Exception:
        pass

    player.shuffle = bool(saved.get("shuffle", False))
    try:
        player.repeat_mode = RepeatMode[saved.get("repeat_mode", "OFF")]
    except KeyError:
        player.repeat_mode = RepeatMode.OFF

    player.set_volume(float(saved.get("volume", player.volume)))

    start_position = float(saved.get("position", 0.0))
    if start_position > 0:
        try:
            player.seek(start_position)
        except Exception:
            pass

    return AppContext(
        player=player,
        settings_service=settings_service,
        playlist_service=playlist_service,
        playlists_data=playlists_data,
        current_playlist_name=playlist_name,
        scanned_songs=songs,
    )


# ---------------------------------------------------------------------------
# Shared playlist-switch helper (GUI keeps its own _apply_playlist; this is
# for the CLI and any other non-GUI frontend)
# ---------------------------------------------------------------------------

def switch_playlist(ctx: AppContext, name: str) -> bool:
    """Switch the player's active playlist.

    Returns True on success, False if the name is not in playlists_data.
    Caller is responsible for any UI refresh (selection highlight, etc.).
    """
    if name not in ctx.playlists_data:
        return False

    songs = _load_playlist_songs(ctx.playlists_data, name)

    if ctx.playlist_service.clean_missing_files(ctx.playlists_data):
        ctx.playlist_service.save(ctx.playlists_data)

    ctx.player.playlist = Playlist(songs)
    ctx.current_playlist_name = name
    return True


# ---------------------------------------------------------------------------
# Shared state persistence
# ---------------------------------------------------------------------------

def save_state(ctx: AppContext) -> None:
    """Persist the current player state to settings.json and playlists.json."""
    ctx.settings_service.save({
        "playlist_index": ctx.player.playlist.current_index,
        "position": ctx.player.get_position() or 0.0,
        "volume": ctx.player.volume,
        "playlist_name": ctx.current_playlist_name,
        "shuffle": ctx.player.shuffle,
        "repeat_mode": ctx.player.repeat_mode.name,
    })
    ctx.playlist_service.save(ctx.playlists_data)
