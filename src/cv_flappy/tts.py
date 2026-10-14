import io
import os
import tempfile
import threading
import wave

import pygame

from .config import (
    TTS_CONFIG_PATH,
    TTS_ENABLED,
    TTS_MODEL_PATH,
)


class Speech:
    """Neural TTS (Piper ONNX). Loads the voice in the background so startup
    stays fast; the first name is spoken once the model is ready."""

    def __init__(self, enabled: bool = TTS_ENABLED):
        self.enabled = enabled and pygame.mixer.get_init() is not None
        self._voice = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._channel: pygame.mixer.Channel | None = None
        if not self.enabled:
            print("TTS disabled: no audio device / mixer unavailable.")
            return
        if not (TTS_MODEL_PATH.is_file() and TTS_CONFIG_PATH.is_file()):
            print(f"TTS disabled: voice not found at {TTS_MODEL_PATH}.")
            self.enabled = False
            return
        try:
            self._channel = pygame.mixer.Channel(pygame.mixer.get_num_channels() - 1)
        except pygame.error:
            self._channel = None
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        try:
            from piper import PiperVoice

            self._voice = PiperVoice.load(
                str(TTS_MODEL_PATH), config_path=str(TTS_CONFIG_PATH)
            )
            print(f"TTS voice ready: {TTS_MODEL_PATH.name}")
        except Exception as exc:
            print(f"TTS disabled: could not load voice ({exc}).")
            self.enabled = False
        finally:
            self._ready.set()

    def say(self, text: str) -> None:
        text = text.strip()
        if not self.enabled or not text:
            return
        self._ready.wait(timeout=10.0)
        voice = self._voice
        if voice is None:
            print("TTS: voice not ready yet, skipping.")
            return
        wav_bytes = self._synthesize(voice, text)
        if wav_bytes is None:
            return
        sound = self._to_sound(wav_bytes)
        if sound is None:
            return
        if self._channel is not None:
            self._channel.stop()
            self._channel.play(sound)
        else:
            sound.play()

    def _synthesize(self, voice, text: str) -> bytes | None:
        buffer = io.BytesIO()
        try:
            with self._lock:
                with wave.open(buffer, "wb") as wav:
                    voice.synthesize_wav(text, wav)
        except Exception as exc:
            print(f"TTS: could not synthesize {text!r} ({exc}).")
            return None
        return buffer.getvalue()

    @staticmethod
    def _to_sound(wav_bytes: bytes) -> pygame.mixer.Sound | None:
        try:
            return pygame.mixer.Sound(file=io.BytesIO(wav_bytes))
        except pygame.error:
            pass
        path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                handle.write(wav_bytes)
                path = handle.name
            return pygame.mixer.Sound(path)
        except (pygame.error, OSError) as exc:
            print(f"TTS: could not play audio ({exc}).")
            return None
        finally:
            if path is not None:
                try:
                    os.unlink(path)
                except OSError:
                    pass
