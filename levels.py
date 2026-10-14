"""Deterministic procedural level generation."""
import hashlib
import math

from settings import WIDTH, CYAN, BLUE, PURPLE, PINK, GOLD, GREEN
from entities.brick import Brick


def _contains_brick(pattern, row, col, rows, cols, level):
    """Describe the preferred geometry for one of six level families."""
    center_col = (cols - 1) / 2

    if pattern == 0:
        # Dense, compact central formation.
        distance = max(
            abs(row - (rows - 1) / 2),
            abs(col - center_col) * 0.72,
        )
        return distance <= 3.5

    if pattern == 1:
        # Triangle widens toward the bottom.
        half_width = 1.0 + row * 0.65
        return abs(col - center_col) <= half_width

    if pattern == 2:
        # Checkerboard.
        return (row + col + level) % 2 == 0

    if pattern == 3:
        # Frame with two inner horizontal bars.
        border = row in (0, rows - 1) or col in (0, cols - 1)
        bars = row in (2, rows - 3) and 2 <= col <= cols - 3
        return border or bars

    if pattern == 4:
        # Continuous horizontal wave ribbon.
        wave_center = center_col + math.sin(
            row * 1.15 + level * 0.25
        ) * 1.8
        return abs(col - wave_center) <= 3

    # Six vertical columns.
    active_columns = (0, 1, 4, 5, 8, 9)
    return col in active_columns


def _variation_key(pattern, row, col, level):
    """Stable tie-breaker that is independent of Python's hash randomization."""
    payload = f"{level}:{pattern}:{row}:{col}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big")


def _shape_priority(pattern, row, col, rows, cols, level):
    """Rank cells by how well they preserve the family geometry."""
    center_row = (rows - 1) / 2
    center_col = (cols - 1) / 2

    if pattern == 0:
        # Expand the dense formation outward from its center.
        return -max(
            abs(row - center_row),
            abs(col - center_col) * 0.72,
        )

    if pattern == 1:
        # Prefer the triangle interior, then its edge, then outside cells.
        half_width = 1.0 + row * 0.65
        return (half_width - abs(col - center_col)) * 10 + row * 0.001

    if pattern == 2:
        # Keep checkerboard parity as the first priority.
        return 100 if (row + col + level) % 2 == 0 else 0

    if pattern == 3:
        border = row in (0, rows - 1) or col in (0, cols - 1)
        bars = row in (2, rows - 3) and 2 <= col <= cols - 3
        if border:
            return 100
        if bars:
            return 90
        edge_distance = min(
            row, rows - 1 - row, col, cols - 1 - col
        )
        return 20 - edge_distance

    if pattern == 4:
        wave_center = center_col + math.sin(
            row * 1.15 + level * 0.25
        ) * 1.8
        return 100 - abs(col - wave_center) * 12

    active_columns = (0, 1, 4, 5, 8, 9)
    if col in active_columns:
        return 100
    distance = min(abs(col - active) for active in active_columns)
    return 40 - distance * 10


def _encoding_cells(rows, cols):
    """Return ten fixed, distributed cells used for unique level signatures."""
    cells = {
        (
            round(bit * (rows - 1) / 9),
            (bit * 3) % cols,
        )
        for bit in range(10)
    }
    if len(cells) != 10:
        raise ValueError("Level encoding cells must be unique.")
    return cells


def _level_code(level):
    """Map levels 1..1000 to distinct 10-bit codes with at least two set bits."""
    if not 1 <= level <= 1000:
        raise ValueError("Unique layouts are supported for levels 1..1000.")

    index = 0
    for code in range(1 << 10):
        if code.bit_count() < 2:
            continue
        if index == level - 1:
            return code
        index += 1

    raise ValueError("No unique layout code available for this level.")


def make_level(level):
    """Generate a deterministic level with unique layouts and controlled count."""
    level = max(1, int(level))
    if level > 1000:
        raise ValueError("Unique layouts are supported for levels 1..1000.")

    cols = 10
    rows = 8
    gap = 8
    margin = 58
    brick_w = (WIDTH - margin * 2 - gap * (cols - 1)) // cols
    brick_h = 24
    pattern = (level - 1) % 6
    palette = [CYAN, BLUE, PURPLE, PINK, GOLD, GREEN]

    # === CONTROLLED BRICK COUNT ===
    target_count = min(58, 42 + (level - 1) // 4)

    # === GUARANTEED UNIQUE SIGNATURE ===
    encoding_cells = _encoding_cells(rows, cols)
    code = _level_code(level)

    ordered_encoding_cells = sorted(encoding_cells)
    encoded_cells = {
        cell
        for bit, cell in enumerate(ordered_encoding_cells)
        if (code >> bit) & 1
    }

    # Keep all signature cells reserved so zero bits remain distinguishable.
    candidates = [
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if (row, col) not in encoding_cells
    ]

    # === GEOMETRY-FIRST SELECTION ===
    candidates.sort(key=lambda cell: (
        -_shape_priority(
            pattern, cell[0], cell[1], rows, cols, level
        ),
        _variation_key(pattern, cell[0], cell[1], level),
        cell[0],
        cell[1],
    ))

    remaining_slots = target_count - len(encoded_cells)
    if remaining_slots < 0 or remaining_slots > len(candidates):
        raise RuntimeError("Invalid brick count for the selected layout.")

    selected_cells = encoded_cells | set(candidates[:remaining_slots])

    if len(selected_cells) != target_count:
        raise RuntimeError(
            f"Expected {target_count} bricks, got {len(selected_cells)}."
        )

    # === SMOOTH HP PROGRESSION ===
    # Total extra HP grows gradually, independently of layout geometry.
    hp_bonus = min(22, (level - 1) // 45)
    hp3_count = min(6, (level - 1) // 150)
    hp2_count = hp_bonus - 2 * hp3_count

    hp_ranked_cells = sorted(
        selected_cells,
        key=lambda cell: (
            _variation_key(pattern, cell[0], cell[1], level),
            cell[0],
            cell[1],
        ),
    )
    hp3_cells = set(hp_ranked_cells[:hp3_count])
    hp2_cells = set(hp_ranked_cells[hp3_count:hp3_count + hp2_count])

    bricks = []
    for row, col in sorted(selected_cells):
        if (row, col) in hp3_cells:
            hp = 3
        elif (row, col) in hp2_cells:
            hp = 2
        else:
            hp = 1

        color = palette[(row + level - 1) % len(palette)]
        bricks.append(Brick(
            margin + col * (brick_w + gap),
            100 + row * (brick_h + 10),
            brick_w,
            brick_h,
            hp,
            color,
        ))

    return bricks
