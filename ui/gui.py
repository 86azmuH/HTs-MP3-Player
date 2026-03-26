import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import tkinter.ttk as ttk

from core.player import PlaybackState, Player, RepeatMode
from core.playlist import Playlist
from core.song import Song
from services.metadata_service import MetadataService


class MP3PlayerGUI:
    def __init__(self, root: tk.Tk, player: Player, settings_service, playlist_service, playlists_data, current_playlist):
        self.root = root
        self.player = player
        self.settings_service = settings_service
        self.playlist_service = playlist_service
        self.playlists_data = playlists_data
        self.current_playlist = current_playlist
        self._is_seeking = False

        root.title("Modular MP3 Player")
        root.geometry("640x460")

        playlist_frame = tk.Frame(root)
        playlist_frame.pack(fill=tk.X, padx=8, pady=4)

        tk.Label(playlist_frame, text="Playlist:").pack(side=tk.LEFT, padx=(0,4))
        self.playlist_combo = ttk.Combobox(playlist_frame, state="readonly")
        self.playlist_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.playlist_combo.bind("<<ComboboxSelected>>", self.on_playlist_select_name)

        self.new_playlist_btn = tk.Button(playlist_frame, text="New", command=self.on_new_playlist)
        self.new_playlist_btn.pack(side=tk.LEFT, padx=4)

        self.delete_playlist_btn = tk.Button(playlist_frame, text="Delete", command=self.on_delete_playlist)
        self.delete_playlist_btn.pack(side=tk.LEFT, padx=4)

        self.song_listbox = tk.Listbox(root)
        self.song_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.song_listbox.bind("<<ListboxSelect>>", self.on_song_select)
        self.song_listbox.bind("<Double-Button-1>", self.on_song_double_click)

        self.song_menu = tk.Menu(self.song_listbox, tearoff=0)
        self.song_menu.add_command(label="Add to playlist", command=self.on_song_menu_add_to_playlist)
        self.song_menu.add_command(label="Remove from playlist", command=self.on_song_menu_remove_from_playlist)
        self.song_listbox.bind("<Button-3>", self.on_song_right_click)

        controls_frame = tk.Frame(root)
        controls_frame.pack(fill=tk.X, padx=8, pady=4)

        self.play_pause_button = tk.Button(controls_frame, text="Play/Pause", command=self.on_play_pause)
        self.play_pause_button.pack(side=tk.LEFT, padx=4)

        self.prev_button = tk.Button(controls_frame, text="Previous", command=self.on_previous)
        self.prev_button.pack(side=tk.LEFT, padx=4)

        self.next_button = tk.Button(controls_frame, text="Next", command=self.on_next)
        self.next_button.pack(side=tk.LEFT, padx=4)

        self.shuffle_button = tk.Button(
            controls_frame,
            text=f"Shuffle: {'On' if self.player.shuffle else 'Off'}",
            command=self.on_toggle_shuffle,
        )
        self.shuffle_button.pack(side=tk.LEFT, padx=4)

        self.repeat_button = tk.Button(
            controls_frame,
            text=f"Repeat: {self.player.repeat_mode.name}",
            command=self.on_cycle_repeat,
        )
        self.repeat_button.pack(side=tk.LEFT, padx=4)

        progress_frame = tk.Frame(root)
        progress_frame.pack(fill=tk.X, padx=8, pady=4)

        self.position_label = tk.Label(progress_frame, text="00:00 / 00:00")
        self.position_label.pack(side=tk.LEFT, padx=4)

        self.progress_scale = tk.Scale(progress_frame, from_=0, to=0, orient=tk.HORIZONTAL, command=self.on_seek)
        self.progress_scale.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=4)
        self.progress_scale.bind("<ButtonPress-1>", self.on_seek_start)
        self.progress_scale.bind("<ButtonRelease-1>", self.on_seek_release)

        self._pending_seek_seconds = None

        volume_frame = tk.Frame(root)
        volume_frame.pack(fill=tk.X, padx=8, pady=4)

        tk.Label(volume_frame, text="Volume").pack(side=tk.LEFT)
        self.volume_scale = tk.Scale(volume_frame, from_=0, to=100, orient=tk.HORIZONTAL, command=self.on_volume_change)
        self.volume_scale.set(int(self.player.volume * 100))
        self.volume_scale.pack(fill=tk.X, expand=True, side=tk.LEFT)

        self.status_label = tk.Label(root, text="Ready", anchor=tk.W)
        self.status_label.pack(fill=tk.X, padx=8, pady=4)

        menu = tk.Menu(root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open Folder...", command=self.on_open_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=root.quit)
        menu.add_cascade(label="File", menu=file_menu)
        root.config(menu=menu)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._autosave_count = 0

        self._update_playlist_combo()
        if self.current_playlist in self.playlists_data:
            self._apply_playlist(self.current_playlist)

        if not self.player.playlist.songs:
            messagebox.showinfo("No songs", "No MP3 files found. Use File > Open Folder to select a directory with MP3s.")

        self.schedule_update()

    def on_open_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        from services.file_service import FileService

        try:
            songs = FileService.scan_mp3_directory(folder)
            self.playlists_data["All songs"] = [str(song.path) for song in songs]
            self.playlist_service.save(self.playlists_data)

            self.player.playlist = Playlist(songs)
            self.current_playlist = "All songs"
            self._update_playlist_combo()
            self.refresh_song_list()
            self.refresh_selection()
            self.status_label.config(text=f"Loaded {len(songs)} songs")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not load songs: {exc}")

    def _update_playlist_combo(self):
        names = sorted(self.playlists_data.keys())
        self.playlist_combo['values'] = names
        if self.current_playlist in names:
            self.playlist_combo.set(self.current_playlist)
        elif names:
            self.current_playlist = names[0]
            self.playlist_combo.set(self.current_playlist)

    def _apply_playlist(self, name):
        self.current_playlist = name
        playlist_paths = self.playlists_data.get(name, [])
        songs = []
        for p in playlist_paths:
            try:
                songs.append(MetadataService.load_song(p))
            except FileNotFoundError:
                continue

        # For empty playlists, show no items (except All songs has its full list)
        if not songs and name == "All songs":
            all_paths = self.playlists_data.get("All songs", [])
            songs = []
            for p in all_paths:
                try:
                    songs.append(MetadataService.load_song(p))
                except FileNotFoundError:
                    continue

        self.player.playlist = Playlist(songs)
        self.refresh_song_list()
        self.refresh_selection()

        # remove missing song entries from the playlist data and save if changed
        if self.playlist_service.clean_missing_files(self.playlists_data):
            self.playlist_service.save(self.playlists_data)

        self.settings_service.save({
            **self.settings_service.load(),
            "playlist_name": name,
            "playlist_index": self.player.playlist.current_index,
        })
        self.playlist_service.save(self.playlists_data)

    def _show_playlist_selector(self, title, prompt, options):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text=prompt).pack(padx=8, pady=8)
        combo = ttk.Combobox(dialog, values=options, state="readonly")
        combo.pack(padx=8, pady=4)
        combo.set(options[0])

        choice = {"value": None}

        def on_ok():
            choice["value"] = combo.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        buttons = tk.Frame(dialog)
        buttons.pack(padx=8, pady=8)
        tk.Button(buttons, text="OK", command=on_ok).pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=4)

        self.root.wait_window(dialog)
        return choice["value"]

    def on_playlist_select_name(self, event):
        selected = self.playlist_combo.get()
        if selected:
            self._apply_playlist(selected)

    def on_new_playlist(self):
        name = tk.simpledialog.askstring("New Playlist", "Playlist name:")
        if not name:
            return
        if name in self.playlists_data:
            messagebox.showwarning("Playlist exists", "Playlist with that name already exists")
            return
        self.playlists_data[name] = []
        self.playlist_service.save(self.playlists_data)
        self._update_playlist_combo()
        self.playlist_combo.set(name)
        self._apply_playlist(name)

    def on_delete_playlist(self):
        if self.current_playlist == "All songs":
            messagebox.showwarning("Cannot delete", "Cannot delete All songs playlist")
            return

        if self.current_playlist not in self.playlists_data:
            return

        del self.playlists_data[self.current_playlist]
        self.playlist_service.save(self.playlists_data)

        self.current_playlist = "All songs" if "All songs" in self.playlists_data else next(iter(self.playlists_data), None)
        self._update_playlist_combo()
        if self.current_playlist:
            self._apply_playlist(self.current_playlist)

    def on_add_selected_to_playlist(self, skip_change=True):
        selected_indices = self.song_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No songs selected", "Please select one or more songs to add.")
            return

        existing_names = [name for name in sorted(self.playlists_data.keys()) if name != "All songs"]
        if not existing_names:
            messagebox.showwarning("No playlists", "Please create a playlist first.")
            return

        target_playlist = self._show_playlist_selector("Add to playlist", "Select playlist", existing_names)
        if not target_playlist:
            return

        if target_playlist == "All songs":
            messagebox.showwarning("Invalid playlist", "Cannot add songs to All songs (it always contains all files).")
            return

        if target_playlist not in self.playlists_data:
            messagebox.showwarning("Playlist not found", "Create the playlist first.")
            return

        for idx in selected_indices:
            if idx < 0 or idx >= len(self.player.playlist.songs):
                continue
            song = self.player.playlist.songs[idx]
            path_str = str(song.path)
            if path_str not in self.playlists_data[target_playlist]:
                self.playlists_data[target_playlist].append(path_str)

        self.playlist_service.save(self.playlists_data)

        if not skip_change and self.current_playlist == target_playlist:
            self._apply_playlist(target_playlist)

    def on_remove_selected_from_playlist(self):
        if self.current_playlist == "All songs":
            messagebox.showwarning("Cannot remove", "All songs cannot be edited.")
            return

        selected_indices = self.song_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No songs selected", "Please select one or more songs to remove.")
            return

        removed = []
        for idx in reversed(selected_indices):
            if idx < 0 or idx >= len(self.player.playlist.songs):
                continue
            song = self.player.playlist.songs[idx]
            path_str = str(song.path)
            if path_str in self.playlists_data[self.current_playlist]:
                self.playlists_data[self.current_playlist].remove(path_str)
                removed.append(song)

        self.playlist_service.save(self.playlists_data)

        if removed:
            self._apply_playlist(self.current_playlist)

    def refresh_song_list(self):
        self.song_listbox.delete(0, tk.END)
        for song in self.player.playlist.songs:
            self.song_listbox.insert(tk.END, song.title)

    def on_song_select(self, event):
        if not self.song_listbox.curselection():
            return
        index = self.song_listbox.curselection()[0]
        self.player.playlist.set_index(index)

    def on_song_double_click(self, event):
        self.on_song_select(event)
        try:
            self.player.stop()
            self.player.play()
        except Exception as exc:
            messagebox.showerror("Playback Error", str(exc))
        self.refresh_selection()
        self.save_settings()

    def on_song_right_click(self, event):
        selection = self.song_listbox.nearest(event.y)
        if selection is not None:
            self.song_listbox.selection_clear(0, tk.END)
            self.song_listbox.selection_set(selection)
        self.song_menu.post(event.x_root, event.y_root)

    def on_song_menu_add_to_playlist(self):
        if self.current_playlist == "All songs":
            self.on_add_selected_to_playlist(skip_change=False)
            return

        self.on_add_selected_to_playlist(skip_change=False)

    def on_song_menu_remove_from_playlist(self):
        if self.current_playlist == "All songs":
            messagebox.showwarning("Cannot remove", "Cannot remove songs from All songs playlist")
            return
        self.on_remove_selected_from_playlist()

    def on_play(self):
        try:
            self.player.play()
        except Exception as exc:
            messagebox.showerror("Playback Error", str(exc))
        self.refresh_selection()
        self.save_settings()

    def on_toggle_shuffle(self):
        self.player.toggle_shuffle()
        self.shuffle_button.config(text=f"Shuffle: {'On' if self.player.shuffle else 'Off'}")
        self.save_settings()

    def on_cycle_repeat(self):
        self.player.cycle_repeat_mode()
        self.repeat_button.config(text=f"Repeat: {self.player.repeat_mode.name}")
        self.save_settings()

    def on_pause(self):
        self.player.pause()
        self.save_settings()

    def on_play_pause(self):
        try:
            if self.player.state == PlaybackState.PLAYING:
                self.player.pause()
            else:
                self.player.play()
        except Exception as exc:
            messagebox.showerror("Playback Error", str(exc))
        self.refresh_selection()
        self.save_settings()

    def on_stop(self):
        self.player.stop()
        self.save_settings()

    def on_next(self):
        try:
            self.player.next()
        except Exception as exc:
            messagebox.showerror("Playback Error", str(exc))
        self.refresh_selection()
        self.save_settings()

    def on_previous(self):
        try:
            self.player.previous()
        except Exception as exc:
            messagebox.showerror("Playback Error", str(exc))
        self.refresh_selection()
        self.save_settings()

    def on_volume_change(self, value):
        self.player.set_volume(float(value) / 100.0)
        self.save_settings()

    def on_seek_start(self, event):
        self._is_seeking = True

    def on_seek(self, value):
        if not self._is_seeking:
            return

        try:
            self._pending_seek_seconds = float(value)
        except (TypeError, ValueError):
            self._pending_seek_seconds = None
            return

        length = self.player.get_length() or 0
        if length > 0 and self._pending_seek_seconds is not None:
            self.position_label.config(text=f"{self._format_time(self._pending_seek_seconds)} / {self._format_time(length)}")

    def on_seek_release(self, event):
        if self._pending_seek_seconds is None:
            self._is_seeking = False
            return

        try:
            self.player.seek(self._pending_seek_seconds)
        except Exception as exc:
            messagebox.showerror("Seek Error", str(exc))

        self._pending_seek_seconds = None
        self._is_seeking = False
        self.save_settings()

    def refresh_selection(self):
        current = self.player.playlist.current_index
        self.song_listbox.selection_clear(0, tk.END)
        if self.player.playlist.songs:
            self.song_listbox.selection_set(current)
            self.song_listbox.activate(current)
            self.song_listbox.see(current)

    @staticmethod
    def _format_time(seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

    def save_settings(self):
        if not self.settings_service:
            return

        playlist_index = self.player.playlist.current_index
        position = self.player.get_position() or 0.0
        volume = self.player.volume

        self.settings_service.save({
            "playlist_index": playlist_index,
            "position": position,
            "volume": volume,
            "playlist_name": self.current_playlist,
            "shuffle": self.player.shuffle,
            "repeat_mode": self.player.repeat_mode.name,
        })
        self.playlist_service.save(self.playlists_data)


    def schedule_update(self):
        self.update_status()
        self.root.after(500, self.schedule_update)

    def on_close(self):
        self.save_settings()
        self.root.destroy()

    def update_status(self):
        self.player.update()

        track = self.player.current_song
        track_name = track.title if track else "No track"

        position = self.player.get_position()
        length = self.player.get_length() or 0

        if length > 0:
            self.progress_scale.config(to=int(length))
            if not self._is_seeking:
                self.progress_scale.set(int(position))
        else:
            self.progress_scale.config(to=0)
            self.progress_scale.set(0)

        self.position_label.config(text=f"{self._format_time(position)} / {self._format_time(length)}")
        self.status_label.config(
            text=(
                f"State: {self.player.state.name} | Track: {track_name} "
                f"| Volume: {int(self.player.volume*100)} "
                f"| Shuffle: {'On' if self.player.shuffle else 'Off'} "
                f"| Repeat: {self.player.repeat_mode.name}"
            )
        )

        # autosave every 2 seconds while playing/paused
        self._autosave_count += 1
        if self._autosave_count >= 4:
            self.save_settings()
            self._autosave_count = 0

