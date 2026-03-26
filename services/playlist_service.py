import json
from pathlib import Path
from typing import Dict, List


class PlaylistService:
    def __init__(self, filename: str = None):
        if filename:
            self.path = Path(filename)
        else:
            self.path = Path(__file__).resolve().parent.parent / "playlists.json"

    def load(self) -> Dict[str, List[str]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
                if isinstance(payload, dict):
                    return {k: list(v) for k, v in payload.items()}
                return {}
        except Exception:
            return {}

    def save(self, playlists: Dict[str, List[str]]):
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(playlists, f, indent=2)
        except Exception as exc:
            print(f"Failed to save playlists: {exc}")

    def get_playlist_names(self, playlists: Dict[str, List[str]]):
        return sorted(playlists.keys())

    def ensure_playlist(self, playlists: Dict[str, List[str]], name: str) -> Dict[str, List[str]]:
        if name not in playlists:
            playlists[name] = []
        return playlists

    def clean_missing_files(self, playlists: Dict[str, List[str]]) -> bool:
        """Remove entries from playlists that no longer exist on disk.

        Returns True if any playlist was modified.
        """
        modified = False
        for name, paths in list(playlists.items()):
            valid_paths = []
            for p in paths:
                try:
                    path_obj = Path(p)
                except Exception:
                    continue
                if path_obj.exists() and path_obj.is_file():
                    valid_paths.append(str(path_obj))
            if len(valid_paths) != len(paths):
                playlists[name] = valid_paths
                modified = True
        return modified
