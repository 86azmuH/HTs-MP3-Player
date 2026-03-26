from services.playlist_service import PlaylistService


def test_playlist_service_load_save(tmp_path):
    p = tmp_path / "playlists.json"
    service = PlaylistService(str(p))

    data = {"All songs": ["/tmp/a.mp3"], "Favorites": ["/tmp/a.mp3"]}
    service.save(data)

    loaded = service.load()
    assert "All songs" in loaded
    assert loaded["Favorites"] == ["/tmp/a.mp3"]


def test_playlist_service_get_names():
    service = PlaylistService()
    names = service.get_playlist_names({"B": [], "A": []})
    assert names == ["A", "B"]
