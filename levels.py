"""Procedural level generation."""
from settings import WIDTH, CYAN, BLUE, PURPLE, PINK, GOLD, GREEN
from entities.brick import Brick


def make_level(level):
    bricks = []
    cols = 10
    gap = 8
    margin = 58
    brick_w = (WIDTH - margin * 2 - gap * (cols - 1)) // cols
    brick_h = 24
    rows = min(4 + level, 8)
    palette = [CYAN, BLUE, PURPLE, PINK, GOLD, GREEN]

    for row in range(rows):
        for col in range(cols):
            # Small gaps add tactical variation after the first sector.
            if level > 1 and (row * 3 + col * 7 + level) % (13 + (level % 4)) == 0:
                continue

            hp = 1
            if level >= 2 and row < 2 and (row + col + level) % 4 == 0:
                hp = 2
            if level >= 4 and (row + col) % 11 == 0:
                hp = 3

            color = palette[(row + level - 1) % len(palette)]
            bricks.append(
                Brick(
                    margin + col * (brick_w + gap),
                    100 + row * (brick_h + 10),
                    brick_w, brick_h, hp, color,
                )
            )
    return bricks
