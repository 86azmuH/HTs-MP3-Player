from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Song:
    path: Path
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    duration: Optional[float] = None

    @staticmethod
    def from_path(path: str) -> "Song":
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Song file not found: {path}")

        title = p.stem
        return Song(path=p, title=title)
