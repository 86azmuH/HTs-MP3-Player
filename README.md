# MP3 Player

This repository contains the full project in one place:

- standalone local player (`gui.py`, `cli.py`)
- FastAPI hub (`device_service/`)
- offline-first controller playback agent (`controller_agent/`)

## First-time setup (copy-paste checklist)

### Python environment note (important)

- Global installs (`python3 -m pip install ...`) can work on some machines.
- On Debian/Raspberry Pi, global installs are often restricted; use a virtual environment for reliable setup.
- `venv` folders are local machine artifacts and should never be committed to git.
- This repo already ignores them (`venv/`, `.venv/`, `env/`).

### Full system setup (hub on Pi, browser/agent controllers elsewhere)

On Pi (hub device):

```bash
# Clone repo
git clone <your-repo-url> ~/mp3_player
cd ~/mp3_player

# Create and activate venv (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install deps
sudo apt update && sudo apt install -y python3 python3-pip python3-pygame python3-mutagen
python3 -m pip install fastapi uvicorn "pydantic<2"

# Add your MP3 files to media/
cp /path/to/your/music/* media/

# Start hub
python3 -m uvicorn device_service.main:app --host 0.0.0.0 --port 8000
```

On controller device (Windows/Mac/Linux):

```bash
# Clone repo
git clone <your-repo-url> ~/mp3_player
cd ~/mp3_player

# Create and activate venv (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install deps
python3 -m pip install fastapi uvicorn "pydantic<2"

# Add same MP3 files
cp /path/to/your/music/* media/

# Run one of:
# Option A: browser controller (open http://<hub-ip>:8000/controller)
python3 -m uvicorn device_service.main:app --host 127.0.0.1 --port 8000

# Option B: local playback that syncs to hub
python3 -m controller_agent.main --device-id controller-1 --hub-url http://<hub-ip>:8000
```

### GUI-only local mode (no hub)

```bash
python3 gui.py
```

### CLI-only local mode (no hub)

```bash
python3 cli.py
```

## Architecture Modes (pick one)

### 1) Full system: API hub on one device + controllers on others

Use this when you want one central API hub (for sync/state) and separate
controller devices.

- Hub device (for example Raspberry Pi): runs `device_service`.
- Controller device(s): run browser UI and/or `controller_agent`.
- Controller devices can keep playing offline and sync when they reconnect.

### 2) CLI-only local mode (no API)

Run only `cli.py` on one machine. Audio plays on that same machine.

### 3) GUI-only local mode (no API)

Run only `gui.py` on one machine. Audio plays on that same machine.

### 4) API-backed GUI-only / CLI-only control mode

- GUI-only control: open browser at `/controller` (web GUI talks to API).
- CLI-only control: use terminal commands (`curl`/PowerShell `Invoke-RestMethod`)
  to call API endpoints.

## Requirements

## Windows (MSYS2)

This project works best with MSYS2 Python 3.12.

Install dependencies from MSYS2 MinGW64 terminal:

```bash
pacman -S mingw-w64-x86_64-python-pygame mingw-w64-x86_64-python-mutagen
```

Install API libs:

```bash
/c/msys64/mingw64/bin/python3.12 -m pip install fastapi uvicorn "pydantic<2"
```

## Raspberry Pi (hub)

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-pygame python3-mutagen
python3 -m pip install fastapi uvicorn "pydantic<2"
```

## Quick Start

## A) Full system (recommended)

### Step 1: run API hub on Pi (or any always-on device)

```bash
python3 -m uvicorn device_service.main:app --host 0.0.0.0 --port 8000
```

### Step 2: connect GUI controller from another device

Open in browser:

```text
http://<hub-ip>:8000/controller
```

### Step 3: optional controller-local playback + offline sync

On controller device:

```bash
python3 -m controller_agent.main --device-id controller-1 --hub-url http://<hub-ip>:8000
```

Behavior:

- local playback continues if hub is down
- local state is saved in `controller_state.db`
- reconnect triggers sync push/pull with conflict handling

## B) CLI-only local mode

MSYS2 bash:

```bash
cd "/c/Users/humze/OneDrive/sharedProgramming/mp3_player"
/c/msys64/mingw64/bin/python3.12 cli.py
```

## C) GUI-only local mode

MSYS2 bash:

```bash
cd "/c/Users/humze/OneDrive/sharedProgramming/mp3_player"
/c/msys64/mingw64/bin/python3.12 gui.py
```

PowerShell:

```powershell
cd C:\Users\humze\OneDrive\sharedProgramming\mp3_player
& 'C:\msys64\mingw64\bin\python3.12.exe' .\gui.py
```

## D) API-backed GUI-only and CLI-only control

### GUI-only control of API

Use browser controller:

```text
http://<hub-ip>:8000/controller
```

### CLI-only control of API (examples)

```bash
curl -X POST http://<hub-ip>:8000/v1/playback/play
curl -X POST http://<hub-ip>:8000/v1/playback/pause
curl -X POST http://<hub-ip>:8000/v1/playback/next
curl -X POST http://<hub-ip>:8000/v1/playback/volume \
  -H "Content-Type: application/json" \
  -d '{"volume":0.6}'
curl http://<hub-ip>:8000/v1/state
```

## Sync API (offline-first)

- `GET /v1/sync/pull?device_id=<id>&since_version=<n>`
- `POST /v1/sync/push`

If `base_version` is stale, API returns `conflict=true` with current canonical
state.

## Playback API endpoints

- `GET /v1/health`
- `GET /v1/state`
- `GET /v1/queue`
- `GET /v1/playlists`
- `POST /v1/playlists/use`
- `POST /v1/playback/play`
- `POST /v1/playback/pause`
- `POST /v1/playback/stop`
- `POST /v1/playback/toggle`
- `POST /v1/playback/next`
- `POST /v1/playback/prev`
- `POST /v1/playback/seek`
- `POST /v1/playback/volume`
- `POST /v1/playback/shuffle/toggle`
- `POST /v1/playback/repeat/cycle`
- `POST /v1/queue/select`
- `POST /v1/queue/play`

## Pi autostart with systemd

Service file: `infra/pi/mp3-device.service`

```bash
sudo cp infra/pi/mp3-device.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mp3-device
sudo systemctl status mp3-device
```

If your path differs, edit `WorkingDirectory` and `ExecStart` in the unit.

## Add new MP3 files

- Copy files into the music folder on the playback device.
- Restart/reload whichever runtime is using that folder (hub or local mode).
- Playlist content comes from `playlists.json`; update it if you use curated
  playlists.

## Tests

```bash
/c/msys64/mingw64/bin/python3.12 -m pytest
```

## Notes

- `pygame` warnings about AVX2 or `pkg_resources` are usually non-fatal.
- Local runtime snapshots: `device_state.db` (hub) and `controller_state.db`
  (controller agent).

## Project Structure

- `core/` domain models and playback logic
- `services/` audio, metadata, playlist, settings services
- `device_service/` FastAPI hub + web controller
- `controller_agent/` offline-first controller playback runtime
- `ui/` UI implementations (`gui.py`, `cli.py`, `gui_app.py`)
- `tests/` unit tests
