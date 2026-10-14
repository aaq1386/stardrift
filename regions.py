"""Space region definitions for STARDRIFT."""

from settings import CYAN, BLUE, PURPLE, PINK, GOLD, GREEN

REGION_LENGTH = 5

REGIONS = (
    {
        "name": "NEBULA",
        "background": (5, 8, 24),
        "glow": (8, 24, 58),
        "star": (130, 190, 255),
        "line": (25, 46, 86),
        "palette": (CYAN, BLUE, PURPLE),
    },
    {
        "name": "CRIMSON",
        "background": (22, 5, 20),
        "glow": (65, 12, 38),
        "star": (255, 155, 175),
        "line": (105, 28, 57),
        "palette": (PINK, (255, 82, 92), GOLD),
    },
    {
        "name": "EMERALD",
        "background": (3, 19, 17),
        "glow": (7, 53, 43),
        "star": (135, 255, 200),
        "line": (20, 82, 67),
        "palette": (GREEN, CYAN, (55, 190, 155)),
    },
    {
        "name": "DEEP SPACE",
        "background": (4, 5, 17),
        "glow": (24, 15, 58),
        "star": (190, 170, 255),
        "line": (55, 39, 105),
        "palette": (PURPLE, BLUE, (155, 125, 255)),
    },
    {
        "name": "SOLAR",
        "background": (23, 13, 4),
        "glow": (65, 37, 8),
        "star": (255, 225, 155),
        "line": (105, 67, 23),
        "palette": (GOLD, (255, 150, 65), PINK),
    },
    {
        "name": "ICE FRONTIER",
        "background": (4, 16, 29),
        "glow": (9, 44, 72),
        "star": (180, 235, 255),
        "line": (27, 83, 119),
        "palette": ((155, 235, 255), CYAN, BLUE),
    },
)


def get_region(level):
    """Return the deterministic region data for a one-based level."""
    level = max(1, int(level))
    index = ((level - 1) // REGION_LENGTH) % len(REGIONS)
    return REGIONS[index]


def get_region_number(level):
    """Return a one-based region number."""
    level = max(1, int(level))
    return ((level - 1) // REGION_LENGTH) % len(REGIONS) + 1
