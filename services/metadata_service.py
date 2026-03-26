from pathlib import Path
from typing import Optional

from core.song import Song

try:
    from mutagen.mp3 import MP3
    _MUTAGEN_AVAILABLE = True
except ImportError:
    _MUTAGEN_AVAILABLE = False


class MetadataService:
    @staticmethod
    def load_song(path: str) -> Song:
        """Create a Song from a file path, loading ID3 metadata if mutagen is available.

        Falls back gracefully for any missing or malformed tags:
        - title  → filename stem
        - artist → None
        - album  → None
        - duration → None (or seconds if audio info is readable)
        """
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Song file not found: {path}")

        title: str = p.stem
        artist: Optional[str] = None
        album: Optional[str] = None
        duration: Optional[float] = None

        if _MUTAGEN_AVAILABLE:
            try:
                audio = MP3(str(p))
                if audio.info:
                    duration = audio.info.length
                tags = audio.tags
                if tags:
                    tit2 = tags.get("TIT2")
                    if tit2:
                        title = str(tit2).strip() or p.stem
                    tpe1 = tags.get("TPE1")
                    if tpe1:
                        artist = str(tpe1).strip() or None
                    talb = tags.get("TALB")
                    if talb:
                        album = str(talb).strip() or None
            except Exception:
                pass  # keep defaults already set above

        return Song(path=p, title=title or p.stem, artist=artist, album=album, duration=duration)
