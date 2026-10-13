"""Reusable helpers and SQLite-backed save functions."""

import json

from database import Database
from settings import WIDTH, HEIGHT
import pygame


def clamp(value, low, high):
    return max(low, min(high, value))


def draw_text(surface, text, font, color, center, shadow=True):
    image = font.render(str(text), True, color)
    rect = image.get_rect(center=(int(center[0]), int(center[1])))

    if shadow:
        shadow_image = font.render(str(text), True, (10, 18, 42))
        surface.blit(shadow_image, rect.move(2, 3))

    surface.blit(image, rect)
    return rect


def load_save():
    """Load personal records from SQLite."""
    profile = Database().get_profile()

    return {
        "high_score": profile["high_score"],
        "best_level": profile["best_level"],
    }


def save_progress(high_score, best_level):
    """Save personal records without lowering existing records."""
    Database().save_progress(high_score, best_level)


def circle_rect_collision(circle, rect):
    """Return (collided, dx, dy), using the closest point on a rectangle."""
    closest_x = clamp(circle.x, rect.left, rect.right)
    closest_y = clamp(circle.y, rect.top, rect.bottom)
    dx = circle.x - closest_x
    dy = circle.y - closest_y

    return (
        dx * dx + dy * dy <= circle.radius * circle.radius,
        dx,
        dy,
    )
# === RUN CHECKPOINTS ===
def save_checkpoint(level, score, lives):
    """Save a restartable checkpoint at the beginning of a level."""
    checkpoint = {
        "level": max(1, int(level)),
        "score": max(0, int(score)),
        "lives": max(1, int(lives)),
    }
    Database().set_setting("run_checkpoint", json.dumps(checkpoint))


def load_checkpoint():
    """Load a valid checkpoint, if one exists."""
    raw = Database().get_setting("run_checkpoint")
    if not raw:
        return None

    try:
        data = json.loads(raw)
        level = int(data["level"])
        score = int(data["score"])
        lives = int(data["lives"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None

    if level < 1 or score < 0 or lives < 1:
        return None

    return {"level": level, "score": score, "lives": lives}


def clear_checkpoint():
    """Clear only the resumable run, preserving profile and purchases."""
    Database().set_setting("run_checkpoint", "")
