import argparse
import tkinter as tk

from bootstrap import build_context, resolve_directory
from ui.gui import MP3PlayerGUI


def main() -> None:
    parser = argparse.ArgumentParser(description="MP3 Player — GUI frontend")
    parser.add_argument("directory", nargs="?", default=None, help="MP3 folder path")
    args = parser.parse_args()

    directory = resolve_directory(args.directory)
    ctx = build_context(str(directory))

    root = tk.Tk()
    gui = MP3PlayerGUI(
        root,
        ctx.player,
        ctx.settings_service,
        ctx.playlist_service,
        ctx.playlists_data,
        ctx.current_playlist_name,
    )
    gui.refresh_song_list()
    gui.refresh_selection()
    root.mainloop()


if __name__ == "__main__":
    main()