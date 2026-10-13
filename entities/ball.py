"""Ball physics and rendering."""
import math
import random
import pygame

from settings import WIDTH, TOP_WALL, CYAN, WHITE
from audio import play_sound


class Ball:
    def __init__(self, x, y, speed, attached=False, color=CYAN, skin=None):
        self.x, self.y = float(x), float(y)
        self.radius = 8
        self.speed = float(speed)
        self.color = tuple(color)
        self.skin = skin
        self._iran_flag_surface = None
        angle = random.choice((-1, 1)) * random.uniform(0.25, 0.65)
        self.vx = math.sin(angle) * self.speed
        self.vy = -math.cos(angle) * self.speed
        self.attached = attached
        self.trail = []

    def launch(self):
        if self.attached:
            self.attached = False
            self.vx = random.choice((-1, 1)) * self.speed * 0.48
            self.vy = -math.sqrt(max(1, self.speed ** 2 - self.vx ** 2))

    def update(self, dt):
        if self.attached:
            return
        # Substeps help prevent tunnelling through thin obstacles at higher speeds.
        distance = math.hypot(self.vx, self.vy) * dt
        steps = max(1, min(20, int(distance / 4) + 1))
        step_dt = dt / steps
        for _ in range(steps):
            self.x += self.vx * step_dt
            self.y += self.vy * step_dt

            if self.x - self.radius < 0:
                self.x = self.radius
                self.vx = abs(self.vx)
                play_sound("hit")
            elif self.x + self.radius > WIDTH:
                self.x = WIDTH - self.radius
                self.vx = -abs(self.vx)
                play_sound("hit")

            if self.y - self.radius < TOP_WALL:
                self.y = TOP_WALL + self.radius
                self.vy = abs(self.vy)
                play_sound("hit")

            self.trail.append((self.x, self.y))
            if len(self.trail) > 7:
                self.trail.pop(0)

    def draw(self, surface):
        trail_color = tuple(max(0, int(channel * 0.55)) for channel in self.color)
        highlight = tuple(
            min(255, int(channel * 0.45 + 255 * 0.55))
            for channel in self.color
        )

        for i, (tx, ty) in enumerate(self.trail):
            radius = max(
                1,
                int(self.radius * (i + 1) / (len(self.trail) + 1) * 0.65),
            )
            pygame.draw.circle(
                surface, trail_color, (int(tx), int(ty)), radius
            )

        center = (int(self.x), int(self.y))
        pygame.draw.circle(
            surface, self.color, center, self.radius + 5, 1
        )

        if self.skin == "iran_flag":
            if self._iran_flag_surface is None:
                size = 24
                flag = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.rect(flag, (35, 155, 85), (0, 0, size, size // 3))
                pygame.draw.rect(flag, (250, 248, 240), (0, size // 3, size, size // 3))
                pygame.draw.rect(flag, (220, 40, 50), (0, 2 * size // 3, size, size // 3))

                # Clip the tricolor to a circle.
                radius = size // 2 - 1
                for px in range(size):
                    for py in range(size):
                        if (px - size // 2) ** 2 + (py - size // 2) ** 2 > radius ** 2:
                            flag.set_at((px, py), (0, 0, 0, 0))

                # Official Iran emblem glyph (Unicode U+262B).
                red = (218, 0, 0)
                cx, cy = size // 2, size // 2
                emblem_font = pygame.font.SysFont("DejaVu Sans", 12, bold=True)
                emblem = emblem_font.render("☫", True, red)
                flag.blit(emblem, emblem.get_rect(center=(cx, cy)))
                self._iran_flag_surface = flag

            surface.blit(
                self._iran_flag_surface,
                self._iran_flag_surface.get_rect(center=center),
            )
            return

        pygame.draw.circle(surface, self.color, center, self.radius)
        pygame.draw.circle(
            surface, highlight, (int(self.x - 2), int(self.y - 2)), 3
        )
