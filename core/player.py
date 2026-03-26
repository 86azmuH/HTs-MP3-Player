import random
from enum import Enum, auto
from typing import Optional, List

from core.playlist import Playlist
from core.song import Song


class PlaybackState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


class RepeatMode(Enum):
    OFF = auto()
    ALL = auto()
    ONE = auto()


class Player:
    def __init__(self, playlist: Playlist, audio_adapter):
        self.playlist = playlist
        self._audio_adapter = audio_adapter
        self.state = PlaybackState.STOPPED
        self.volume = 1.0
        self.shuffle = False
        self.repeat_mode = RepeatMode.OFF
        self._shuffle_history: List[int] = []

    @property
    def current_song(self) -> Optional[Song]:
        return self.playlist.current_song

    def _load_current_song(self) -> None:
        song = self.current_song
        if song is None:
            raise RuntimeError("No song selected in playlist")
        self._audio_adapter.load(str(song.path))

    def load_current_song(self) -> None:
        self._load_current_song()

    def play(self) -> None:
        if self.current_song is None:
            raise RuntimeError("Playlist is empty")
        if self.state == PlaybackState.PAUSED:
            self._audio_adapter.unpause()
            self.state = PlaybackState.PLAYING
            return

        self._load_current_song()
        self._audio_adapter.play()
        self._audio_adapter.set_volume(self.volume)
        self.state = PlaybackState.PLAYING

    def pause(self) -> None:
        if self.state != PlaybackState.PLAYING:
            return
        self._audio_adapter.pause()
        self.state = PlaybackState.PAUSED

    def stop(self) -> None:
        if self.state == PlaybackState.STOPPED:
            return
        self._audio_adapter.stop()
        self.state = PlaybackState.STOPPED

    def toggle_play_pause(self) -> None:
        if self.state == PlaybackState.PLAYING:
            self.pause()
        else:
            self.play()

    def toggle_shuffle(self) -> None:
        self.shuffle = not self.shuffle
        self._shuffle_history.clear()

    def cycle_repeat_mode(self) -> None:
        modes = list(RepeatMode)
        current_idx = modes.index(self.repeat_mode)
        self.repeat_mode = modes[(current_idx + 1) % len(modes)]

    def _advance_next(self) -> None:
        """Move playlist index to the next song, respecting shuffle."""
        if self.shuffle:
            song_count = len(self.playlist.songs)
            if song_count > 1:
                current = self.playlist.current_index
                self._shuffle_history.append(current)
                candidates = [i for i in range(song_count) if i != current]
                self.playlist.set_index(random.choice(candidates))
            else:
                # Only one song: no shuffle possible, wrap in place
                self.playlist.next()
        else:
            self.playlist.next()

    def next(self, *, natural_end: bool = False) -> None:
        """Advance to the next song.

        natural_end=True  → song ended on its own; obeys repeat_mode.
        natural_end=False → manual press; always wraps to the next song.
        """
        if self.playlist.is_empty():
            return

        if natural_end:
            if self.repeat_mode == RepeatMode.ONE:
                # Replay the same song from the start
                self.stop()
                self.play()
                return
            elif self.repeat_mode == RepeatMode.OFF:
                if self.playlist.is_last:
                    # End of playlist with no repeat — just stop
                    self.stop()
                    return
                # Not at the last song yet: fall through to advance
            # RepeatMode.ALL falls through to advance (wraps naturally)

        self._advance_next()
        self.stop()
        self.play()

    def previous(self) -> None:
        if self.playlist.is_empty():
            return

        if self.shuffle and self._shuffle_history:
            prev_index = self._shuffle_history.pop()
            self.playlist.set_index(prev_index)
        else:
            self.playlist.previous()

        self.stop()
        self.play()

    def seek(self, seconds: float) -> None:
        if self.current_song is None:
            raise RuntimeError("Playlist is empty")

        self._load_current_song()
        playing = self.state == PlaybackState.PLAYING
        self._audio_adapter.set_position(seconds, playing=playing)

        if playing:
            self.state = PlaybackState.PLAYING
        else:
            self.state = PlaybackState.PAUSED

    def get_position(self) -> float:
        try:
            return self._audio_adapter.get_position()
        except Exception:
            return 0.0

    def get_length(self):
        try:
            return self._audio_adapter.get_length()
        except Exception:
            return None

    def is_current_song_finished(self, threshold: float = 0.5) -> bool:
        length = self.get_length()
        if length is None or length <= 0:
            return False

        position = self.get_position()
        return self.state == PlaybackState.PLAYING and position >= (length - threshold)

    def update(self):
        if self.is_current_song_finished():
            self.next(natural_end=True)

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        self._audio_adapter.set_volume(self.volume)
