"""Headless CLI frontend for the MP3 player.

Proves that core/Player can be driven by a non-Tkinter frontend.
No Tkinter is imported here.

Usage:
    python ui/cli.py [directory]
    python -m ui.cli [directory]
"""

import argparse
import sys
import threading
from pathlib import Path

# Support both invocation styles:
# 1) python -m ui.cli
# 2) python ui/cli.py
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from bootstrap import AppContext, build_context, resolve_directory, save_state, switch_playlist


# ---------------------------------------------------------------------------
# Background update loop (replaces Tkinter's root.after timer)
# ---------------------------------------------------------------------------

def _start_update_thread(ctx: AppContext) -> threading.Event:
    """Start a daemon thread that calls player.update() every ~0.5 s.

    Uses threading.Event.wait() instead of time.sleep() so the thread wakes
    up immediately when stop_event is set, giving a clean shutdown.
    """
    stop_event = threading.Event()

    def _loop() -> None:
        while not stop_event.is_set():
            try:
                ctx.player.update()
            except Exception:
                pass
            stop_event.wait(0.5)  # interruptible; exits quickly on set()

    t = threading.Thread(target=_loop, daemon=True, name="player-update")
    t.start()
    return stop_event


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _fmt(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def _print_status(ctx: AppContext) -> None:
    p = ctx.player
    song = p.current_song
    position = p.get_position()
    length = p.get_length() or 0
    count = len(p.playlist.songs)
    idx = p.playlist.current_index

    print(f"State:    {p.state.name}")
    print(f"Playlist: {ctx.current_playlist_name}")
    if song:
        print(f"Track:    {song.title}")
        print(f"Index:    {idx + 1}/{count}")
        if song.artist:
            print(f"Artist:   {song.artist}")
        if song.album:
            print(f"Album:    {song.album}")
        print(f"Position: {_fmt(position)} / {_fmt(length)}")
    else:
        print("Track:    (none)")
    print(f"Volume:   {int(p.volume * 100)}%")
    print(f"Shuffle:  {'On' if p.shuffle else 'Off'}")
    print(f"Repeat:   {p.repeat_mode.name}")


def _print_list(ctx: AppContext) -> None:
    songs = ctx.player.playlist.songs
    current = ctx.player.playlist.current_index
    if not songs:
        print("  (empty playlist)")
        return
    for i, song in enumerate(songs):
        marker = "*" if i == current else " "
        artist_part = f" — {song.artist}" if song.artist else ""
        print(f"{marker} [{i}] {song.title}{artist_part}")


_HELP = """\
Commands:
  help                  Show this help
  status                Show current player state
  list                  List songs in the active playlist
  play                  Start / resume playback
  pause                 Pause playback
  toggle                Toggle play / pause
  stop                  Stop playback
  next                  Skip to next track
  prev                  Go to previous track
  shuffle               Toggle shuffle mode
  repeat                Cycle repeat mode (OFF → ALL → ONE → OFF)
  seek <seconds>        Seek to position in seconds
  vol <0-1>             Set volume (e.g. vol 0.7)
  select <index>        Select track by index without playing
  play_index <index>    Select track by index and play immediately
  playlist              Show current playlist name
  playlists             List all available playlists
  use_playlist <name>   Switch to a different playlist
  quit / exit           Save state and exit
"""


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

def _handle_command(cmd: str, arg: str, ctx: AppContext) -> bool:
    """Process one CLI command.  Returns False when the loop should exit."""
    p = ctx.player

    if cmd in ("quit", "exit"):
        return False

    elif cmd == "help":
        print(_HELP)

    elif cmd == "status":
        _print_status(ctx)

    elif cmd == "list":
        _print_list(ctx)

    elif cmd == "play":
        try:
            p.play()
            song = p.current_song
            print(f"Playing: {song.title if song else '(nothing)'}")
        except Exception as e:
            print(f"Error: {e}")

    elif cmd == "pause":
        p.pause()
        print("Paused.")

    elif cmd == "toggle":
        try:
            p.toggle_play_pause()
            print(f"State: {p.state.name}")
        except Exception as e:
            print(f"Error: {e}")

    elif cmd == "stop":
        p.stop()
        print("Stopped.")

    elif cmd == "next":
        try:
            p.next()
            song = p.current_song
            print(f"Now playing: {song.title if song else '(nothing)'}")
        except Exception as e:
            print(f"Error: {e}")

    elif cmd == "prev":
        try:
            p.previous()
            song = p.current_song
            print(f"Now playing: {song.title if song else '(nothing)'}")
        except Exception as e:
            print(f"Error: {e}")

    elif cmd == "shuffle":
        p.toggle_shuffle()
        print(f"Shuffle: {'On' if p.shuffle else 'Off'}")

    elif cmd == "repeat":
        p.cycle_repeat_mode()
        print(f"Repeat: {p.repeat_mode.name}")

    elif cmd == "seek":
        try:
            seconds = float(arg)
        except ValueError:
            print("Usage: seek <seconds>")
            return True
        try:
            p.seek(seconds)
            print(f"Seeked to {_fmt(seconds)}")
        except Exception as e:
            print(f"Error: {e}")

    elif cmd == "vol":
        try:
            volume = float(arg)
        except ValueError:
            print("Usage: vol <0-1>")
            return True
        if not 0.0 <= volume <= 1.0:
            print("Volume must be between 0 and 1.")
            return True
        p.set_volume(volume)
        print(f"Volume: {int(volume * 100)}%")

    elif cmd == "select":
        try:
            index = int(arg)
        except ValueError:
            print("Usage: select <index>")
            return True
        count = len(p.playlist.songs)
        if count == 0:
            print("Playlist is empty.")
            return True
        try:
            p.playlist.set_index(index)
            song = p.current_song
            print(f"Selected [{index}]: {song.title if song else '(none)'}")
        except IndexError:
            print(f"Index out of range. Valid range: 0–{count - 1}.")

    elif cmd == "play_index":
        try:
            index = int(arg)
        except ValueError:
            print("Usage: play_index <index>")
            return True
        count = len(p.playlist.songs)
        if count == 0:
            print("Playlist is empty.")
            return True
        try:
            p.playlist.set_index(index)
            p.stop()
            p.play()
            song = p.current_song
            print(f"Playing [{index}]: {song.title if song else '(none)'}")
        except IndexError:
            print(f"Index out of range. Valid range: 0–{count - 1}.")
        except Exception as e:
            print(f"Error: {e}")

    elif cmd == "playlist":
        print(f"Current playlist: {ctx.current_playlist_name}")

    elif cmd == "playlists":
        names = sorted(ctx.playlists_data.keys())
        for name in names:
            marker = "*" if name == ctx.current_playlist_name else " "
            print(f"{marker} {name}")

    elif cmd == "use_playlist":
        if not arg:
            print("Usage: use_playlist <name>")
            return True
        if switch_playlist(ctx, arg):
            p.stop()
            print(f"Switched to '{arg}'  ({len(p.playlist.songs)} songs)")
        else:
            available = ", ".join(sorted(ctx.playlists_data.keys()))
            print(f"Playlist not found: '{arg}'")
            print(f"Available: {available}")

    else:
        print(f"Unknown command: '{cmd}'. Type 'help' for available commands.")

    return True


# ---------------------------------------------------------------------------
# Main REPL
# ---------------------------------------------------------------------------

def run_cli(ctx: AppContext) -> None:
    stop_event = _start_update_thread(ctx)
    print("MP3 Player CLI — type 'help' for commands, 'quit' to exit.")

    try:
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue

            parts = line.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if not _handle_command(cmd, arg, ctx):
                break
    finally:
        stop_event.set()
        save_state(ctx)
        print("State saved. Goodbye.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="MP3 Player — CLI frontend")
    parser.add_argument("directory", nargs="?", default=None, help="MP3 folder path")
    args = parser.parse_args()

    try:
        directory = resolve_directory(args.directory)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    ctx = build_context(str(directory))
    run_cli(ctx)


if __name__ == "__main__":
    main()
