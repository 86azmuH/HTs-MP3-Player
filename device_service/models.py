from typing import List, Optional

from pydantic import BaseModel, Field


class PlaybackActionResponse(BaseModel):
    ok: bool = True
    state_version: int
    queue_version: int
    message: str


class SeekRequest(BaseModel):
    position_seconds: float = Field(ge=0)


class VolumeRequest(BaseModel):
    volume: float = Field(ge=0, le=1)


class SelectQueueItemRequest(BaseModel):
    index: int = Field(ge=0)
    base_version: Optional[int] = None


class PlayQueueItemRequest(BaseModel):
    index: int = Field(ge=0)
    base_version: Optional[int] = None


class UsePlaylistRequest(BaseModel):
    name: str
    base_version: Optional[int] = None


class QueueItem(BaseModel):
    index: int
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    duration: Optional[float] = None
    path: str
    is_current: bool = False


class QueueResponse(BaseModel):
    queue_version: int
    playlist_name: str
    items: List[QueueItem]


class PlaylistListResponse(BaseModel):
    names: List[str]
    current_playlist_name: str
    queue_version: int


class StateResponse(BaseModel):
    status: str
    current_song_title: Optional[str] = None
    current_song_artist: Optional[str] = None
    current_song_album: Optional[str] = None
    current_song_path: Optional[str] = None
    playlist_name: str
    playlist_index: int
    playlist_length: int
    volume: float
    shuffle: bool
    repeat_mode: str
    position_seconds: float
    length_seconds: Optional[float] = None
    state_version: int
    queue_version: int


class SyncState(BaseModel):
    current_song_path: Optional[str] = None
    playlist_name: Optional[str] = None
    playlist_index: int = Field(default=0, ge=0)
    queue_paths: List[str] = Field(default_factory=list)
    status: str = "stopped"
    position_seconds: float = Field(default=0.0, ge=0)
    volume: float = Field(default=1.0, ge=0, le=1)
    shuffle: bool = False
    repeat_mode: str = "OFF"
    updated_at_ms: Optional[int] = None


class SyncPullResponse(BaseModel):
    ok: bool = True
    changed: bool
    global_version: int
    state: SyncState


class SyncPushRequest(BaseModel):
    device_id: str = Field(min_length=1)
    base_version: Optional[int] = Field(default=None, ge=1)
    state: SyncState


class SyncPushResponse(BaseModel):
    ok: bool = True
    applied: bool
    conflict: bool = False
    global_version: int
    state: SyncState
    message: str
