from pathlib import Path
from typing import List, Optional

from core.song import Song


class Playlist:
    def __init__(self, songs: Optional[List[Song]] = None):
        self._songs: List[Song] = songs.copy() if songs else []
        self._index = 0

    @property
    def songs(self) -> List[Song]:
        return self._songs

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def current_song(self) -> Optional[Song]:
        return self._songs[self._index] if self._songs else None

    @property
    def length(self) -> int:
        return len(self._songs)

    @property
    def is_first(self) -> bool:
        return self._index == 0 and self._songs

    @property
    def is_last(self) -> bool:
        return self._songs and self._index == len(self._songs) - 1

    def add_song(self, song: Song) -> None:
        self._songs.append(song)

    def remove_song(self, song: Song) -> None:
        if song in self._songs:
            idx = self._songs.index(song)
            self._songs.remove(song)
            if self._songs:
                self._index = min(self._index, len(self._songs) - 1)
            else:
                self._index = 0

    def next(self) -> Optional[Song]:
        if not self._songs:
            return None
        self._index = (self._index + 1) % len(self._songs)
        return self.current_song

    def previous(self) -> Optional[Song]:
        if not self._songs:
            return None
        self._index = (self._index - 1) % len(self._songs)
        return self.current_song

    def set_index(self, index: int) -> Optional[Song]:
        if not self._songs:
            return None
        if index < 0 or index >= len(self._songs):
            raise IndexError("Playlist index out of range")
        self._index = index
        return self.current_song

    def clear(self) -> None:
        self._songs.clear()
        self._index = 0

    def is_empty(self) -> bool:
        return len(self._songs) == 0
