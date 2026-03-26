import pytest
from pathlib import Path

from core.song import Song
from services.metadata_service import MetadataService


def test_song_from_path_valid(tmp_path):
    p = tmp_path / "test.mp3"
    p.write_text("dummy")

    song = Song.from_path(str(p))
    assert song.path == p
    assert song.title == "test"


def test_song_from_path_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Song.from_path(str(tmp_path / "missing.mp3"))


# ---------------------------------------------------------------------------
# MetadataService — fallback behaviour on non-real MP3 files
# ---------------------------------------------------------------------------

def test_metadata_service_title_falls_back_to_stem(tmp_path):
    """A file with no valid ID3 tags falls back to the filename stem."""
    p = tmp_path / "my_song.mp3"
    p.write_bytes(b"\x00" * 100)  # not a real MP3

    song = MetadataService.load_song(str(p))

    assert song.title == "my_song"
    assert song.artist is None
    assert song.album is None


def test_metadata_service_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        MetadataService.load_song(str(tmp_path / "missing.mp3"))


def test_metadata_service_duration_none_for_invalid_file(tmp_path):
    p = tmp_path / "bad.mp3"
    p.write_bytes(b"\xFF" * 50)

    song = MetadataService.load_song(str(p))
    # duration may be None or a float; must not raise
    assert song.duration is None or isinstance(song.duration, float)

