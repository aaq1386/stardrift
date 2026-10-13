"""Player paddle and temporary defensive effects."""

import math
import pygame

from settings import WIDTH, HEIGHT, CYAN, WHITE, BLUE
from utils import clamp


class Paddle:
    BASE_WIDTH = 116
    BASE_SPEED = 620
    WIDE_POWERUP_WIDTH = 164

    def __init__(self, width_level=0, speed_level=0):
        self.width_level = max(0, min(5, int(width_level)))
        self.speed_level = max(0, min(5, int(speed_level)))

        # Permanent upgrades affect the normal paddle dimensions.
        self.base_width = round(
            self.BASE_WIDTH * (1 + 0.08 * self.width_level)
        )
        self.wide_width = max(
            self.WIDE_POWERUP_WIDTH,
            round(self.base_width * 1.08),
        )
        self.width = self.base_width
        self.height = 14
        self.speed = self.BASE_SPEED * (1 + 0.07 * self.speed_level)

        self.x = WIDTH / 2 - self.width / 2
        self.y = HEIGHT - 55
        self.wide_timer = 0.0
        self.shield_timer = 0.0

    @property
    def rect(self):
        return pygame.Rect(
            round(self.x), round(self.y), self.width, self.height
        )

    def update(self, dt):
        keys = pygame.key.get_pressed()
        direction = int(
            keys[pygame.K_RIGHT] or keys[pygame.K_d]
        ) - int(
            keys[pygame.K_LEFT] or keys[pygame.K_a]
        )

        self.x += direction * self.speed * dt

        if self.wide_timer > 0:
            self.wide_timer = max(0.0, self.wide_timer - dt)

        self.width = (
            self.wide_width
            if self.wide_timer > 0
            else self.base_width
        )

        self.x = clamp(self.x, 12, WIDTH - self.width - 12)

        if self.shield_timer > 0:
            self.shield_timer = max(0.0, self.shield_timer - dt)

    def move_to_mouse(self, mouse_x):
        self.x = clamp(
            mouse_x - self.width / 2,
            12,
            WIDTH - self.width - 12,
        )

    def draw(self, surface):
        rect = self.rect

        for grow, color in (
            (12, (20, 45, 105)),
            (6, (20, 110, 165)),
        ):
            glow_rect = rect.inflate(grow * 2, grow)
            pygame.draw.rect(
                surface, color, glow_rect, border_radius=12
            )

        pygame.draw.rect(surface, CYAN, rect, border_radius=7)
        pygame.draw.rect(
            surface,
            WHITE,
            (
                rect.x + 14,
                rect.y + 2,
                max(4, rect.width - 28),
                3,
            ),
            border_radius=2,
        )

        if self.shield_timer > 0:
            pygame.draw.arc(
                surface,
                BLUE,
                (
                    rect.x - 10,
                    rect.y - 20,
                    rect.width + 20,
                    54,
                ),
                math.pi,
                math.tau,
                4,
            )
