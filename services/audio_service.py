from abc import ABC, abstractmethod


class AudioAdapter(ABC):
    @abstractmethod
    def load(self, filepath: str):
        raise NotImplementedError

    @abstractmethod
    def play(self):
        raise NotImplementedError

    @abstractmethod
    def pause(self):
        raise NotImplementedError

    @abstractmethod
    def unpause(self):
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        raise NotImplementedError

    @abstractmethod
    def set_volume(self, volume: float):
        raise NotImplementedError

    @abstractmethod
    def get_position(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_length(self):
        raise NotImplementedError

    @abstractmethod
    def set_position(self, seconds: float, playing: bool = False):
        raise NotImplementedError


class DummyAudioAdapter(AudioAdapter):
    def __init__(self):
        self.loaded_file = None
        self.is_paused = False
        self.position = 0.0
        self.duration = 180.0

    def load(self, filepath: str):
        self.loaded_file = filepath
        self.position = 0.0
        print(f"[DummyAudioAdapter] loaded {filepath}")

    def play(self):
        if not self.loaded_file:
            raise RuntimeError("No file loaded")
        print(f"[DummyAudioAdapter] play {self.loaded_file}")

    def pause(self):
        print("[DummyAudioAdapter] pause")
        self.is_paused = True

    def unpause(self):
        if not self.is_paused:
            return
        print("[DummyAudioAdapter] unpause")
        self.is_paused = False

    def stop(self):
        print("[DummyAudioAdapter] stop")
        self.position = 0.0

    def set_volume(self, volume: float):
        print(f"[DummyAudioAdapter] volume {volume}")

    def get_position(self) -> float:
        return self.position

    def get_length(self):
        return self.duration

    def set_position(self, seconds: float, playing: bool = False):
        self.position = max(0.0, min(self.duration, seconds))
        self.is_paused = not playing
        print(f"[DummyAudioAdapter] seek to {self.position}, playing={playing}")


class PygameAudioAdapter(AudioAdapter):
    def __init__(self):
        try:
            import pygame
        except ImportError as ex:
            raise RuntimeError("pygame is required for PygameAudioAdapter", ex)

        pygame.mixer.init()
        self._pygame = pygame
        self._track_length = None
        self._position = 0.0
        self._is_playing = False

    def load(self, filepath: str):
        self._pygame.mixer.music.load(filepath)
        self._track_length = None
        self._position = 0.0
        self._is_playing = False
        try:
            from mutagen.mp3 import MP3

            audio = MP3(filepath)
            self._track_length = audio.info.length
        except Exception:
            self._track_length = None

        if self._track_length is None:
            try:
                sound = self._pygame.mixer.Sound(filepath)
                self._track_length = sound.get_length()
            except Exception:
                self._track_length = None

    def play(self):
        # resume from current position
        if self._position is not None and self._position > 0:
            self._pygame.mixer.music.play(start=self._position)
        else:
            self._pygame.mixer.music.play()
        self._is_playing = True

    def pause(self):
        # capture position to keep sync
        pos = self._pygame.mixer.music.get_pos()
        if pos >= 0:
            self._position += pos / 1000.0
        self._pygame.mixer.music.pause()
        self._is_playing = False

    def unpause(self):
        self._pygame.mixer.music.unpause()
        self._is_playing = True

    def stop(self):
        self._pygame.mixer.music.stop()
        self._position = 0.0
        self._is_playing = False

    def set_volume(self, volume: float):
        self._pygame.mixer.music.set_volume(volume)

    def get_position(self) -> float:
        if self._is_playing:
            pos = self._pygame.mixer.music.get_pos()
            if pos < 0:
                return self._position
            return self._position + pos / 1000.0
        return self._position

    def get_length(self):
        return self._track_length

    def set_position(self, seconds: float, playing: bool = False):
        self._position = max(0.0, seconds)
        self._pygame.mixer.music.stop()
        if playing:
            self._pygame.mixer.music.play(start=self._position)
            self._is_playing = True
        else:
            # set in place without letting it run until play()
            self._pygame.mixer.music.play(start=self._position)
            self._pygame.mixer.music.pause()
            self._is_playing = False

