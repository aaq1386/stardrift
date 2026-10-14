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
    rows = 8
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

    # Assign a unique 10-bit code with at least two set bits.
    # Reserve all ten top-row cells so zero bits cannot be selected by filling.
    candidates.sort()
    code = -1
    code_index = -1

    for candidate_code in range(1 << 10):
        if candidate_code.bit_count() < 2:
            continue
        code_index += 1
        if code_index == level - 1:
            code = candidate_code
            break

    if code < 0:
        raise ValueError("No unique layout code available for this level.")

    # === DISTRIBUTED UNIQUENESS ENCODING ===
    # Spread the ten encoding cells across all rows instead of
    # forcing the entire top row to carry the level code.
    encoding_cells = {
        (
            round(bit * (rows - 1) / 9),
            (bit * 3) % cols,
        )
        for bit in range(10)
    }

    if len(encoding_cells) != 10:
        raise ValueError("Level encoding cells must be unique.")

    encoded_cells = {
        cell
        for bit, cell in enumerate(sorted(
            encoding_cells,
            key=lambda cell: (cell[0], cell[1]),
        ))
        if (code >> bit) & 1
    }

    selected = [
        item for item in candidates
        if (item[2], item[3]) in encoded_cells
    ]

    remaining = [
        item for item in candidates
        if (item[2], item[3]) not in encoding_cells
    ]
    selected.extend(remaining[:target_count - len(selected)])

    bricks = []
    for _, _, row, col in selected:
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
