"""Procedural stars, particles, and floating score labels."""
import math
import random
import pygame

from settings import WIDTH, HEIGHT, WHITE
from utils import clamp

class Star:
    def __init__(self):
        self.x = random.uniform(0, WIDTH)
        self.y = random.uniform(0, HEIGHT)
        self.speed = random.uniform(12, 70)
        self.radius = random.choice((1, 1, 1, 2))
        self.phase = random.uniform(0, math.tau)

    def update(self, dt):
        self.y += self.speed * dt
        self.phase += dt * random.uniform(0.4, 1.2)
        if self.y > HEIGHT:
            self.y = 0
            self.x = random.uniform(0, WIDTH)

    def draw(self, surface, elapsed):
        glow = 100 + int(90 * (0.5 + 0.5 * math.sin(self.phase + elapsed)))
        color = (min(255, glow // 2), min(255, glow), min(255, glow + 35))
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), self.radius)


class Particle:
    def __init__(self, x, y, color, speed=None):
        self.x, self.y = float(x), float(y)
        angle = random.uniform(0, math.tau)
        velocity = random.uniform(55, 250) if speed is None else random.uniform(speed * 0.45, speed)
        self.vx = math.cos(angle) * velocity
        self.vy = math.sin(angle) * velocity
        self.life = self.max_life = random.uniform(0.22, 0.65)
        self.radius = random.uniform(1.5, 4.0)
        self.color = color

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= max(0, 1 - 1.8 * dt)
        self.vy *= max(0, 1 - 1.8 * dt)
        self.life -= dt

    def draw(self, surface):
        if self.life <= 0:
            return
        alpha = clamp(self.life / self.max_life, 0, 1)
        radius = max(1, int(self.radius * alpha))
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), radius)


class FloatingText:
    def __init__(self, x, y, text, color=WHITE):
        self.x, self.y = x, y
        self.text, self.color = text, color
        self.life = 0.8

    def update(self, dt):
        self.y -= 34 * dt
        self.life -= dt

    def draw(self, surface, font):
        if self.life > 0:
            image = font.render(self.text, True, self.color)
            image.set_alpha(int(255 * clamp(self.life / 0.8, 0, 1)))
            surface.blit(image, (int(self.x), int(self.y)))
