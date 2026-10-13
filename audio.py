"""Procedurally generated sound effects; audio is optional."""
import math
import pygame

AUDIO_AVAILABLE = False
try:
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


def toggle_sound():
    global sound_enabled
    sound_enabled = not sound_enabled
    return sound_enabled


def play_sound(name):
    sound = SOUNDS.get(name)
    if sound_enabled and sound is not None:
        try:
            sound.play()
        except pygame.error:
            pass
