from pathlib import Path
from typing import List

from core.song import Song
from services.metadata_service import MetadataService


class FileService:
    @staticmethod
    def scan_mp3_directory(directory: str) -> List[Song]:
        base = Path(directory)
        if not base.exists() or not base.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        songs = []
        for entry in sorted(base.rglob("*.mp3"), key=lambda p: p.name.lower()):
            if entry.is_file():
                try:
                    songs.append(MetadataService.load_song(str(entry)))
                except Exception:
                    continue
        return songs
