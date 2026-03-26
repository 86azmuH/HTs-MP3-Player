# MP3 Player — Detailed Architecture Documentation

This document describes the current architecture of the MP3 player codebase in implementation-level detail. It covers the modular layering, shared bootstrap path, GUI and CLI frontends, playback state machine, persistence, and resilience behavior.

## 1. Architectural Goals

- Keep business logic in `core/`, not in frontends.
- Keep external/system interaction in `services/`.
- Support multiple frontends (Tkinter GUI and headless CLI) against the same `Player` API.
- Keep startup, restore, and persistence behavior shared across frontends.
- Preserve robust behavior for missing files, empty directories, and adapter failures.

## 2. Project Structure

```text
mp3_player/
├── main.py
├── bootstrap.py
├── playlists.json
├── settings.json
├── DETAILED_ARCHITECTURE.md
├── core/
│   ├── song.py
│   ├── playlist.py
│   └── player.py
├── services/
│   ├── audio_service.py
│   ├── file_service.py
│   ├── metadata_service.py
│   ├── playlist_service.py
│   └── settings_service.py
├── ui/
│   ├── gui.py
│   └── cli.py
└── tests/
    ├── test_player.py
    ├── test_playlist.py
    ├── test_playlist_service.py
    ├── test_song.py
    └── test_bootstrap.py
```

## 3. Layering and Boundaries

- `core/`
  - Owns domain types and playback behavior.
  - Does not import `ui/` or `services/`.
- `services/`
  - Owns filesystem/audio/persistence/metadata interaction.
  - Can import `core/` types.
- `bootstrap.py`
  - Shared runtime composition and restore logic.
  - No GUI behavior.
- `ui/gui.py`
  - Tkinter presentation and event bindings.
- `ui/cli.py`
  - Headless command loop presentation.

Both frontends call shared helpers from `bootstrap.py` and drive the same `Player` methods.

## 4. Core Domain Model

### 4.1 `Song` (`core/song.py`)

`Song` is a dataclass with:
- `path: Path`
- `title: str`
- `artist: Optional[str]`
- `album: Optional[str]`
- `duration: Optional[float]`

`Song.from_path(path)` is retained as a minimal fallback constructor (title from stem), while production loading uses `MetadataService.load_song()`.

### 4.2 `Playlist` (`core/playlist.py`)

`Playlist` owns ordered songs plus current index pointer.

Key behavior:
- `next()` wraps modulo length.
- `previous()` wraps modulo length.
- `set_index(i)` validates bounds.
- Empty playlist always behaves safely and returns `None` where applicable.

### 4.3 `Player` (`core/player.py`)

Enums:
- `PlaybackState`: `STOPPED`, `PLAYING`, `PAUSED`
- `RepeatMode`: `OFF`, `ALL`, `ONE`

Player state:
- `playlist`
- `_audio_adapter`
- `state`
- `volume`
- `shuffle`
- `repeat_mode`
- `_shuffle_history` (stack of prior indices used by shuffle mode)

Command surface:
- `play()`, `pause()`, `stop()`, `toggle_play_pause()`
- `next(natural_end=False)`, `previous()`
- `seek(seconds)`, `set_volume(volume)`
- `toggle_shuffle()`, `cycle_repeat_mode()`
- `update()` for natural song-end handling

Important behavior:
- Manual `next()` always advances and wraps; shuffle uses random non-current candidate when possible.
- `previous()` in shuffle mode uses actual history first, then sequential fallback.
- Natural-end behavior comes through `next(natural_end=True)` and obeys repeat mode:
  - `OFF`: stop at last song
  - `ALL`: advance and wrap
  - `ONE`: replay current song

## 5. Service Layer

### 5.1 `AudioAdapter` and implementations (`services/audio_service.py`)

`AudioAdapter` defines the playback contract:
- `load`, `play`, `pause`, `unpause`, `stop`
- `set_volume`, `get_position`, `get_length`, `set_position`

Implementations:
- `DummyAudioAdapter`: predictable no-op style fallback/test adapter.
- `PygameAudioAdapter`: real playback backend using `pygame.mixer`, with duration lookup via mutagen where possible.

### 5.2 `MetadataService` (`services/metadata_service.py`)

`MetadataService.load_song(path)` creates `Song` using safe metadata extraction:
- Title (`TIT2`) with fallback to file stem
- Artist (`TPE1`)
- Album (`TALB`)
- Duration from audio info when available

Any metadata parsing failure falls back safely.

### 5.3 `FileService` (`services/file_service.py`)

`scan_mp3_directory(directory)`:
- Validates directory
- Recursively finds `*.mp3`
- Sorts deterministically by `name.lower()`
- Loads songs via `MetadataService.load_song()`
- Skips unreadable entries safely

### 5.4 `PlaylistService` (`services/playlist_service.py`)

Responsibilities:
- Load/save `playlists.json`
- Ensure structure validity
- `clean_missing_files()` to remove dead file entries

### 5.5 `SettingsService` (`services/settings_service.py`)

Responsibilities:
- Load/save `settings.json`
- Return empty dict on missing/corrupt file

## 6. Shared Bootstrap (`bootstrap.py`)

`bootstrap.py` is the central shared runtime wiring module used by both frontends.

### 6.1 `AppContext`

Dataclass carrying:
- `player`
- `settings_service`
- `playlist_service`
- `playlists_data`
- `current_playlist_name`
- `scanned_songs`

### 6.2 `resolve_directory(explicit_path=None)`

Directory selection policy:
1. explicit arg if provided
2. `<app_base>/media` (`_MEIPASS` when frozen, project dir otherwise)
3. fallback to `cwd` if default is unavailable

### 6.3 `create_audio_adapter()`

- Tries `PygameAudioAdapter`
- Falls back to `DummyAudioAdapter` with warning

### 6.4 `build_context(directory, audio_adapter=None)`

Shared startup sequence:
1. Scan songs from directory
2. Load settings and playlists
3. Clean dead playlist entries
4. Rebuild system playlist `All songs` from scan
5. Choose active playlist from settings, fallback to `All songs`
6. Reconstruct playlist songs via metadata-aware loader
7. Restore index if valid
8. Create player and preload song if possible
9. Restore shuffle, repeat, volume, position
10. Return `AppContext`

### 6.5 `switch_playlist(ctx, name)`

Frontend-agnostic playlist switch helper:
- Validates name
- Rebuilds `Playlist` from stored paths with metadata loader
- Cleans missing entries if needed
- Replaces `ctx.player.playlist`
- Updates `ctx.current_playlist_name`

### 6.6 `save_state(ctx)`

Shared persistence writer used by non-GUI frontend:
- Saves playlist index, position, volume
- Saves playlist name, shuffle, repeat mode
- Persists `playlists_data`

## 7. GUI Frontend (`main.py` + `ui/gui.py`)

### 7.1 `main.py`

`main.py` is now a thin launcher:
1. Parse optional directory argument
2. `resolve_directory()`
3. `build_context()`
4. Create Tk root and `MP3PlayerGUI`
5. Enter Tk event loop

### 7.2 GUI update loop

`ui/gui.py` calls `player.update()` every 500 ms via Tkinter `after()` and refreshes progress/status.

### 7.3 GUI persistence

`save_settings()` keeps settings synchronized during interaction and on close.

## 8. CLI Frontend (`ui/cli.py`)

`ui/cli.py` is a second frontend that proves headless control against the same core.

### 8.1 No Tkinter dependency

The CLI imports only:
- `bootstrap` helpers/context
- standard library modules (`argparse`, `threading`, etc.)

### 8.2 Invocation support

The CLI supports:
- `python ui/cli.py [directory]`
- `python -m ui.cli [directory]`

When run as a script path, it adjusts `sys.path` to include project root so `bootstrap` imports resolve.

### 8.3 Background update thread

A daemon thread calls `ctx.player.update()` every 0.5s using `Event.wait(0.5)`.

Properties:
- Does not block command input
- Handles natural-end playback behavior in CLI mode
- Stops cleanly by setting stop event on exit

### 8.4 Command set

Supported commands:
- `help`
- `status`
- `list`
- `play`
- `pause`
- `toggle`
- `stop`
- `next`
- `prev`
- `shuffle`
- `repeat`
- `seek <seconds>`
- `vol <0-1>`
- `select <index>`
- `play_index <index>`
- `playlist`
- `playlists`
- `use_playlist <name>`
- `quit` / `exit`

### 8.5 CLI status output

Reports:
- State
- Playlist name
- Track title
- Index/total
- Optional artist/album
- Position / length
- Volume
- Shuffle
- Repeat

### 8.6 CLI list output

Prints one song per line with index and selected marker (`*`).

### 8.7 CLI exit behavior

On `quit`/`exit`/interrupt:
- stop update thread
- call `save_state(ctx)`
- print shutdown message

## 9. All Songs System Playlist Rules

`All songs` is treated as system-managed:
- rebuilt from scan each startup
- deterministic order via `name.lower()` sort key
- not user-curated
- cannot be deleted in GUI
- remains available for both frontends

## 10. Persistence Contract

### 10.1 `settings.json`

Current keys:
- `playlist_name`
- `playlist_index`
- `position`
- `volume`
- `shuffle`
- `repeat_mode`

### 10.2 `playlists.json`

Format: `Dict[str, List[str]]`
- includes user playlists and `All songs`
- dead entries are cleaned safely

Both GUI and CLI preserve this contract.

## 11. Error Handling and Resilience

Handled safely:
- empty startup folder
- missing files in playlists
- bad commands in CLI
- bad seek/volume/index arguments
- unknown playlist names
- unavailable audio backend (pygame fallback)
- corrupt/missing settings/playlists JSON

## 12. Test Coverage Snapshot

- `tests/test_player.py`
  - repeat modes, natural-end behavior, shuffle history, command behavior
- `tests/test_song.py`
  - metadata fallback safety
- `tests/test_playlist.py`
  - wraparound navigation
- `tests/test_playlist_service.py`
  - persistence round-trip
- `tests/test_bootstrap.py`
  - shared helper behavior:
    - playlist switching
    - save-state content
    - playlist name/index persistence path

## 13. Current Frontend Comparison

- GUI frontend:
  - event-driven via Tk
  - visual list/progress controls
  - timer via `root.after()`
- CLI frontend:
  - command-driven via stdin
  - background update thread
  - same `Player` semantics and persistence model

This demonstrates that playback behavior is frontend-agnostic and that command/control separation is now practical for future targets (for example, embedded/physical controls).
