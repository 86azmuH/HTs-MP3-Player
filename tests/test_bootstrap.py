"""Tests for shared bootstrap helpers (AppContext, switch_playlist, save_state)."""

import pytest
from pathlib import Path

from core.player import Player, RepeatMode
from core.playlist import Playlist
from core.song import Song
from services.audio_service import DummyAudioAdapter
from services.settings_service import SettingsService
from services.playlist_service import PlaylistService
from bootstrap import AppContext, switch_playlist, save_state


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write_dummy_songs(tmp_path: Path, names: list) -> list[Song]:
    """Create zero-byte .mp3 files and return Song objects."""
    songs = []
    for name in names:
        p = tmp_path / f"{name}.mp3"
        p.write_bytes(b"\x00" * 10)
        songs.append(Song(path=p, title=name))
    return songs


def _make_ctx(tmp_path: Path, song_names=("a", "b", "c")) -> AppContext:
    songs = _write_dummy_songs(tmp_path, list(song_names))
    playlists_data = {
        "All songs": [str(s.path) for s in songs],
        "Favs": [str(songs[0].path)],
    }
    settings_service = SettingsService(str(tmp_path / "settings.json"))
    playlist_service = PlaylistService(str(tmp_path / "playlists.json"))
    player = Player(Playlist(list(songs)), DummyAudioAdapter())
    return AppContext(
        player=player,
        settings_service=settings_service,
        playlist_service=playlist_service,
        playlists_data=playlists_data,
        current_playlist_name="All songs",
        scanned_songs=songs,
    )


# ---------------------------------------------------------------------------
# switch_playlist
# ---------------------------------------------------------------------------

def test_switch_playlist_to_known_name(tmp_path):
    ctx = _make_ctx(tmp_path)
    result = switch_playlist(ctx, "Favs")
    assert result is True
    assert ctx.current_playlist_name == "Favs"
    # "Favs" only has the first song
    assert len(ctx.player.playlist.songs) == 1


def test_switch_playlist_to_all_songs(tmp_path):
    ctx = _make_ctx(tmp_path)
    switch_playlist(ctx, "Favs")   # move away first
    result = switch_playlist(ctx, "All songs")
    assert result is True
    assert ctx.current_playlist_name == "All songs"
    assert len(ctx.player.playlist.songs) == 3


def test_switch_playlist_unknown_returns_false(tmp_path):
    ctx = _make_ctx(tmp_path)
    result = switch_playlist(ctx, "Does Not Exist")
    assert result is False
    # original playlist name unchanged
    assert ctx.current_playlist_name == "All songs"


def test_switch_playlist_index_resets_to_zero(tmp_path):
    ctx = _make_ctx(tmp_path)
    ctx.player.playlist.set_index(2)
    switch_playlist(ctx, "Favs")
    assert ctx.player.playlist.current_index == 0


def test_switch_playlist_missing_file_skipped(tmp_path):
    """Entries pointing to deleted files are silently dropped."""
    ctx = _make_ctx(tmp_path)
    ghost_path = str(tmp_path / "ghost.mp3")
    ctx.playlists_data["Ghost"] = [ghost_path]
    result = switch_playlist(ctx, "Ghost")
    assert result is True
    assert len(ctx.player.playlist.songs) == 0


# ---------------------------------------------------------------------------
# save_state
# ---------------------------------------------------------------------------

def test_save_state_writes_all_keys(tmp_path):
    ctx = _make_ctx(tmp_path)
    ctx.player.set_volume(0.42)
    ctx.player.shuffle = True
    ctx.player.cycle_repeat_mode()  # OFF → ALL
    ctx.player.playlist.set_index(1)

    save_state(ctx)

    saved = ctx.settings_service.load()
    assert saved["volume"] == pytest.approx(0.42)
    assert saved["shuffle"] is True
    assert saved["repeat_mode"] == "ALL"
    assert saved["playlist_name"] == "All songs"
    assert saved["playlist_index"] == 1


def test_save_state_persists_repeat_mode(tmp_path):
    ctx = _make_ctx(tmp_path)
    ctx.player.cycle_repeat_mode()  # ALL
    ctx.player.cycle_repeat_mode()  # ONE
    save_state(ctx)
    saved = ctx.settings_service.load()
    assert saved["repeat_mode"] == "ONE"


def test_save_state_round_trips_playlist_name(tmp_path):
    ctx = _make_ctx(tmp_path)
    switch_playlist(ctx, "Favs")
    save_state(ctx)
    saved = ctx.settings_service.load()
    assert saved["playlist_name"] == "Favs"
