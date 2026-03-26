import json
from pathlib import Path


class SettingsService:
    def __init__(self, filename: str = None):
        if filename:
            self.path = Path(filename)
        else:
            self.path = Path(__file__).resolve().parent.parent / "settings.json"

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, settings: dict):
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as exc:
            print(f"Failed to save settings: {exc}")
