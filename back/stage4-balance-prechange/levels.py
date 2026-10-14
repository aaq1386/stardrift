"""Deterministic procedural level generation."""
import math

from settings import WIDTH, CYAN, BLUE, PURPLE, PINK, GOLD, GREEN
from entities.brick import Brick


def _contains_brick(pattern, row, col, rows, cols, level):
    """Choose a brick position for one of six level families."""
    if pattern == 0:
        # Dense grid with predictable gaps.
        return (row * 3 + col * 7 + level) % (13 + level % 4) != 0

    if pattern == 1:
        # Diamond that widens toward the middle rows.
        center_row = (rows - 1) / 2
        center_col = (cols - 1) / 2
        span = 1.5 + (rows / 2 - abs(row - center_row))
        return abs(col - center_col) <= span

    if pattern == 2:
        # Alternating checkerboard.
        return (row + col + level) % 2 == 0

    if pattern == 3:
        # Fortress walls with intermittent inner defenses.
        border = row in (0, rows - 1) or col in (0, 1, cols - 2, cols - 1)
        inner = row % 3 == 1 and 3 <= col <= cols - 4
        return border or inner

    if pattern == 4:
        # Wavy bands with a level-dependent phase.
        center = (cols - 1) / 2 + math.sin(row * 1.15 + level * 0.25) * 1.8
        return abs(col - center) <= 3

    # Six: separated vertical columns.
    active_columns = (0, 1, 4, 5, 8, 9)
    return (
        col in active_columns
        and (row + level) % 5 != 0
    )


def make_level(level):
    level = max(1, int(level))
    bricks = []
    cols = 10
    gap = 8
    margin = 58
    brick_w = (WIDTH - margin * 2 - gap * (cols - 1)) // cols
    brick_h = 24
    rows = min(4 + level, 8)
    pattern = (level - 1) % 6
    palette = [CYAN, BLUE, PURPLE, PINK, GOLD, GREEN]

    for row in range(rows):
        for col in range(cols):
            if not _contains_brick(pattern, row, col, rows, cols, level):
                continue

            hp = 1
            if level >= 2 and (row * 3 + col * 5 + level) % 7 == 0:
                hp = 2
            if level >= 4 and (row + col * 2 + level) % 17 == 0:
                hp = 3

            color = palette[(row + level - 1) % len(palette)]
            bricks.append(
                Brick(
                    margin + col * (brick_w + gap),
                    100 + row * (brick_h + 10),
                    brick_w,
                    brick_h,
                    hp,
                    color,
                )
            )

    return bricks
