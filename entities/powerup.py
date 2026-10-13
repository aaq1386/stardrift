"""Falling power-up pickups."""
import pygame

from settings import GOLD, BLUE, PINK, PURPLE
from utils import draw_text

class PowerUp:
    TYPES = ("wide", "shield", "multiball", "slow")
    COLORS = {"wide": GOLD, "shield": BLUE, "multiball": PINK, "slow": PURPLE}
    LABELS = {"wide": "W", "shield": "S", "multiball": "M", "slow": "T"}

    def __init__(self, x, y, kind=None):
        self.x, self.y = float(x), float(y)
        self.kind = kind or __import__("random").choice(self.TYPES)
        self.radius = 13
        self.speed = 135

    def update(self, dt):
        self.y += self.speed * dt

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.radius), int(self.y - self.radius),
            self.radius * 2, self.radius * 2,
        )

    def draw(self, surface, font):
        color = self.COLORS[self.kind]
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), self.radius + 4, 1)
        pygame.draw.circle(surface, (15, 20, 48), (int(self.x), int(self.y)), self.radius)
        draw_text(surface, self.LABELS[self.kind], font, color, (self.x, self.y), False)
