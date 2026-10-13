"""Breakable brick entity."""
import pygame
from settings import WHITE


class Brick:
    def __init__(self, x, y, width, height, hp, color, kind="normal"):
        self.rect = pygame.Rect(x, y, width, height)
        self.hp = hp
        self.max_hp = hp
        self.color = color
        self.kind = kind
        self.flash = 0.0

    def hit(self):
        self.hp -= 1
        self.flash = 0.09
        return self.hp <= 0

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)

    def draw(self, surface):
        color = WHITE if self.flash else self.color
        dark = tuple(max(0, c // 3) for c in color)
        highlight = tuple(min(255, c + 45) for c in color)
        pygame.draw.rect(surface, dark, self.rect.inflate(6, 6), border_radius=7)
        pygame.draw.rect(surface, color, self.rect, border_radius=5)
        pygame.draw.rect(
            surface, highlight,
            (self.rect.x + 4, self.rect.y + 3, self.rect.width - 8, 2),
            border_radius=2,
        )
        if self.max_hp > 1:
            for i in range(self.hp):
                pygame.draw.circle(
                    surface, WHITE,
                    (self.rect.right - 8 - i * 7, self.rect.centery), 2,
                )
