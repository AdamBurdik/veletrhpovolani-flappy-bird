import pygame

from .config import (
    ASSETS_DIR,
    SFX_DIE,
    SFX_FLAP,
    SFX_POINT,
    SOUND_ENABLED,
    SOUND_VOLUME,
)


class SoundManager:
    def __init__(self, enabled: bool = SOUND_ENABLED, volume: float = SOUND_VOLUME):
        self.volume = volume
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._channels: dict[str, pygame.mixer.Channel] = {}
        self._available = enabled and pygame.mixer.get_init() is not None
        if not self._available:
            return
        pygame.mixer.set_num_channels(max(8, pygame.mixer.get_num_channels()))
        for index, (name, filename) in enumerate(
            (
                ("flap", SFX_FLAP),
                ("point", SFX_POINT),
                ("die", SFX_DIE),
            )
        ):
            path = ASSETS_DIR / filename
            try:
                sound = pygame.mixer.Sound(str(path))
            except (pygame.error, FileNotFoundError) as exc:
                print(f"Could not load sound {path}: {exc}")
                continue
            sound.set_volume(volume)
            self._sounds[name] = sound
            self._channels[name] = pygame.mixer.Channel(index)

    def play(self, name: str) -> None:
        channel = self._channels.get(name)
        if channel is None:
            return
        channel.stop()
        channel.play(self._sounds[name])
