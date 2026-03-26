import pytest

from core.player import Player, PlaybackState, RepeatMode
from core.playlist import Playlist
from core.song import Song
from services.audio_service import DummyAudioAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(*titles: str) -> tuple[Player, DummyAudioAdapter]:
    songs = [Song(path=f"/tmp/{t}.mp3", title=t) for t in titles]
    adapter = DummyAudioAdapter()
    player = Player(Playlist(songs), adapter)
    return player, adapter


def _simulate_song_end(player: Player, adapter: DummyAudioAdapter) -> None:
    """Force the adapter to look like the song finished, then call update()."""
    adapter.position = adapter.duration  # position == length
    player.update()


# ---------------------------------------------------------------------------
# Basic play / pause / stop
# ---------------------------------------------------------------------------

def test_player_play_pause_stop():
    player, _ = _make_player("s1")
    player.play()
    assert player.state == PlaybackState.PLAYING

    player.pause()
    assert player.state == PlaybackState.PAUSED

    player.play()
    assert player.state == PlaybackState.PLAYING

    player.stop()
    assert player.state == PlaybackState.STOPPED


def test_toggle_play_pause():
    player, _ = _make_player("s1")
    player.play()
    player.toggle_play_pause()
    assert player.state == PlaybackState.PAUSED
    player.toggle_play_pause()
    assert player.state == PlaybackState.PLAYING


# ---------------------------------------------------------------------------
# Volume bounds
# ---------------------------------------------------------------------------

def test_player_set_volume_bounds():
    player, _ = _make_player("s1")
    player.set_volume(1.5)
    assert player.volume == 1.0
    player.set_volume(-1)
    assert player.volume == 0.0


# ---------------------------------------------------------------------------
# Manual next / previous — always wrap
# ---------------------------------------------------------------------------

def test_manual_next_wraps_last_to_first():
    player, _ = _make_player("a", "b", "c")
    player.play()
    player.playlist.set_index(2)
    player.next()
    assert player.playlist.current_index == 0


def test_manual_previous_wraps_first_to_last():
    player, _ = _make_player("a", "b", "c")
    player.play()
    player.previous()
    assert player.playlist.current_index == 2


# ---------------------------------------------------------------------------
# Repeat mode — natural end behaviour
# ---------------------------------------------------------------------------

def test_natural_end_repeat_off_stops_at_last():
    player, adapter = _make_player("a", "b", "c")
    player.repeat_mode = RepeatMode.OFF
    player.playlist.set_index(2)  # last song
    player.play()

    _simulate_song_end(player, adapter)

    assert player.state == PlaybackState.STOPPED
    assert player.playlist.current_index == 2  # stayed on last


def test_natural_end_repeat_off_advances_when_not_last():
    player, adapter = _make_player("a", "b", "c")
    player.repeat_mode = RepeatMode.OFF
    player.playlist.set_index(1)
    player.play()

    _simulate_song_end(player, adapter)

    assert player.playlist.current_index == 2
    assert player.state == PlaybackState.PLAYING


def test_natural_end_repeat_all_wraps():
    player, adapter = _make_player("a", "b", "c")
    player.repeat_mode = RepeatMode.ALL
    player.playlist.set_index(2)  # last song
    player.play()

    _simulate_song_end(player, adapter)

    assert player.playlist.current_index == 0
    assert player.state == PlaybackState.PLAYING


def test_natural_end_repeat_one_replays():
    player, adapter = _make_player("a", "b", "c")
    player.repeat_mode = RepeatMode.ONE
    player.playlist.set_index(1)
    player.play()
    original_index = player.playlist.current_index

    _simulate_song_end(player, adapter)

    assert player.playlist.current_index == original_index
    assert player.state == PlaybackState.PLAYING


# ---------------------------------------------------------------------------
# cycle_repeat_mode
# ---------------------------------------------------------------------------

def test_cycle_repeat_mode():
    player, _ = _make_player("s1")
    assert player.repeat_mode == RepeatMode.OFF
    player.cycle_repeat_mode()
    assert player.repeat_mode == RepeatMode.ALL
    player.cycle_repeat_mode()
    assert player.repeat_mode == RepeatMode.ONE
    player.cycle_repeat_mode()
    assert player.repeat_mode == RepeatMode.OFF


# ---------------------------------------------------------------------------
# 1-song playlist edge cases
# ---------------------------------------------------------------------------

def test_one_song_repeat_off_natural_end_stops():
    player, adapter = _make_player("only")
    player.repeat_mode = RepeatMode.OFF
    player.play()
    _simulate_song_end(player, adapter)
    assert player.state == PlaybackState.STOPPED


def test_one_song_repeat_all_natural_end_replays():
    player, adapter = _make_player("only")
    player.repeat_mode = RepeatMode.ALL
    player.play()
    _simulate_song_end(player, adapter)
    assert player.state == PlaybackState.PLAYING
    assert player.playlist.current_index == 0


def test_one_song_repeat_one_natural_end_replays():
    player, adapter = _make_player("only")
    player.repeat_mode = RepeatMode.ONE
    player.play()
    _simulate_song_end(player, adapter)
    assert player.state == PlaybackState.PLAYING
    assert player.playlist.current_index == 0


# ---------------------------------------------------------------------------
# Shuffle next (picks different song)
# ---------------------------------------------------------------------------

def test_shuffle_next_picks_different_song():
    player, _ = _make_player("s1", "s2", "s3")
    player.shuffle = True
    player.play()
    original = player.playlist.current_index
    player.next()
    assert player.playlist.current_index != original


# ---------------------------------------------------------------------------
# Shuffle history — previous goes back
# ---------------------------------------------------------------------------

def test_shuffle_previous_uses_history():
    player, _ = _make_player("a", "b", "c")
    player.shuffle = True
    player.playlist.set_index(0)
    player.play()

    player.next()  # records index 0 in history, moves to something else
    idx_after_next = player.playlist.current_index

    player.previous()  # should pop history → back to 0
    assert player.playlist.current_index == 0


def test_shuffle_previous_fallback_when_no_history():
    """With no shuffle history, previous() falls back to sequential previous."""
    player, _ = _make_player("a", "b", "c")
    player.shuffle = True
    player.playlist.set_index(1)
    player.play()

    assert len(player._shuffle_history) == 0
    player.previous()
    # sequential previous from index 1 → index 0
    assert player.playlist.current_index == 0


def test_toggle_shuffle_clears_history():
    player, _ = _make_player("a", "b", "c")
    player.shuffle = True
    player.playlist.set_index(0)
    player.play()
    player.next()  # populates history
    assert len(player._shuffle_history) > 0

    player.toggle_shuffle()  # turns shuffle off, clears history
    assert player._shuffle_history == []

