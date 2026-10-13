"""Reusable helpers and SQLite-backed save functions."""

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
