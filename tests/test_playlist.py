from core.song import Song
from core.playlist import Playlist


def test_playlist_navigation():
    songs = [Song(path="/tmp/1.mp3", title="1"), Song(path="/tmp/2.mp3", title="2"), Song(path="/tmp/3.mp3", title="3")]
    playlist = Playlist(songs)

    assert playlist.current_song.title == "1"

    playlist.next()
    assert playlist.current_song.title == "2"

    playlist.next()
    assert playlist.current_song.title == "3"

    playlist.next()
    assert playlist.current_song.title == "1"

    playlist.previous()
    assert playlist.current_song.title == "3"


def test_playlist_set_index():
    playlist = Playlist([Song(path="/tmp/a.mp3", title="a"), Song(path="/tmp/b.mp3", title="b")])
    playlist.set_index(1)
    assert playlist.current_song.title == "b"
