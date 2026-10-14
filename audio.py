"""Procedurally generated sound effects and optional background music."""
import math
from pathlib import Path

import pygame

AUDIO_AVAILABLE = False
MUSIC_AVAILABLE = False
MUSIC_PATH = Path(__file__).resolve().parent / "assets" / "music" / "OutThere.ogg"

try:
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    AUDIO_AVAILABLE = True
except pygame.error:
    AUDIO_AVAILABLE = False


def make_tone(frequency=440, duration=0.07, volume=0.18):
    if not AUDIO_AVAILABLE:
        return None

    try:
        import array

        sample_rate = 22050
        count = max(1, int(sample_rate * duration))
        samples = array.array("h")

        for i in range(count):
            envelope = min(1.0, i / max(1, count * 0.06)) * (1 - i / count)
            value = int(
                32767 * volume * envelope
                * math.sin(2 * math.pi * frequency * i / sample_rate)
            )
            samples.append(value)

        return pygame.mixer.Sound(buffer=samples.tobytes())
    except (pygame.error, ImportError, ValueError):
        return None


SOUNDS = {
    "hit": make_tone(660, 0.045, 0.13),
    "brick": make_tone(390, 0.055, 0.12),
    "power": make_tone(880, 0.12, 0.16),
    "lose": make_tone(145, 0.24, 0.18),
    "win": make_tone(990, 0.18, 0.16),
}

sound_enabled = True


def start_music():
    """Start looping background music when audio is available."""
    global MUSIC_AVAILABLE

    if not AUDIO_AVAILABLE or not MUSIC_PATH.is_file():
        MUSIC_AVAILABLE = False
        return False

    try:
        pygame.mixer.music.load(str(MUSIC_PATH))
        pygame.mixer.music.set_volume(0.35)
        pygame.mixer.music.play(-1)
        MUSIC_AVAILABLE = True

        if not sound_enabled:
            pygame.mixer.music.pause()

        return True
    except pygame.error:
        MUSIC_AVAILABLE = False
        return False


def toggle_sound():
    """Toggle sound effects and background music together."""
    global sound_enabled

    sound_enabled = not sound_enabled

    if AUDIO_AVAILABLE:
        try:
            if sound_enabled:
                if MUSIC_AVAILABLE:
                    pygame.mixer.music.unpause()
            else:
                if MUSIC_AVAILABLE:
                    pygame.mixer.music.pause()
        except pygame.error:
            pass

    return sound_enabled


def play_sound(name):
    sound = SOUNDS.get(name)

    if sound_enabled and sound is not None:
        try:
            sound.play()
        except pygame.error:
            pass
