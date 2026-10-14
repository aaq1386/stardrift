"""Deterministic procedural level generation."""
import hashlib
import math

from settings import WIDTH, CYAN, BLUE, PURPLE, PINK, GOLD, GREEN
from entities.brick import Brick


def _contains_brick(pattern, row, col, rows, cols, level):
    """Choose a brick position for one of six level families."""
    if pattern == 0:
        return (row * 3 + col * 7 + level) % (13 + level % 4) != 0

    if pattern == 1:
        center_row = (rows - 1) / 2
        center_col = (cols - 1) / 2
        span = 1.5 + (rows / 2 - abs(row - center_row))
        return abs(col - center_col) <= span

    if pattern == 2:
        return (row + col + level) % 2 == 0

    if pattern == 3:
        border = row in (0, rows - 1) or col in (0, 1, cols - 2, cols - 1)
        inner = row % 3 == 1 and 3 <= col <= cols - 4
        return border or inner

    if pattern == 4:
        center = (cols - 1) / 2 + math.sin(row * 1.15 + level * 0.25) * 1.8
        return abs(col - center) <= 3

    active_columns = (0, 1, 4, 5, 8, 9)
    return col in active_columns and (row + level) % 5 != 0


def _variation_key(pattern, row, col, level):
    """Return a stable, level-specific tie-breaker for layout variation."""
    payload = f"{level}:{pattern}:{row}:{col}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big")


def make_level(level):
    """Generate a deterministic level with a controlled difficulty curve."""
    level = max(1, int(level))
    cols = 10
    gap = 8
    margin = 58
    brick_w = (WIDTH - margin * 2 - gap * (cols - 1)) // cols
    brick_h = 24
    rows = min(4 + level, 8)
    pattern = (level - 1) % 6
    palette = [CYAN, BLUE, PURPLE, PINK, GOLD, GREEN]

    # === CONTROLLED BRICK COUNT ===
    target_count = min(58, 42 + (level - 1) // 4)

    candidates = []
    for row in range(rows):
        for col in range(cols):
            preferred = _contains_brick(pattern, row, col, rows, cols, level)
            candidates.append((
                not preferred,
                _variation_key(pattern, row, col, level),
                row,
                col,
            ))

    # Encode the level number in ten dedicated top-row positions.
    # This guarantees distinct position layouts for levels 1 through 1000.
    candidates.sort()
    encoded_cells = {
        (0, bit)
        for bit in range(10)
        if ((level - 1) >> bit) & 1
    }

    selected = [
        item for item in candidates
        if (item[2], item[3]) in encoded_cells
    ]

    # Fill remaining slots while preserving the preferred family geometry.
    remaining = [
        item for item in candidates
        if (item[2], item[3]) not in encoded_cells
    ]
    selected.extend(remaining[:target_count - len(selected)])

    bricks = []
    for _, _, row, col in selected:
        color = palette[(row + level - 1) % len(palette)]
        bricks.append(
            Brick(
                margin + col * (brick_w + gap),
                100 + row * (brick_h + 10),
                brick_w,
                brick_h,
                1,
                color,
            )
        )

    # === GRADUAL BRICK DURABILITY ===
    # Add one extra HP every three levels, distributed across bricks.
    extra_hp = min(4 * len(bricks), (level - 1) // 3)

    ranked_bricks = sorted(
        bricks,
        key=lambda brick: (
            brick.rect.y * 37
            + brick.rect.x * 19
            + level * 11
            + brick.rect.x * brick.rect.y * 7
        ) % 1009,
    )

    for index in range(extra_hp):
        ranked_bricks[index % len(ranked_bricks)].hp += 1

    return bricks
