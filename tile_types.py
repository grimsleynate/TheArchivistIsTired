from typing import Tuple

import numpy as np  # type: ignore
import color;

# Tile graphics structured type compatible with Console.tiles_rgb.
graphic_dt = np.dtype(
    [
        ("ch", np.int32),  # Unicode codepoint.
        ("fg", "3B"),  # 3 unsigned bytes, for RGB colors.
        ("bg", "3B"),
    ]
)

# Tile struct used for statically defined tile data.
tile_dt = np.dtype(
    [
        ("walkable", bool),  # True if this tile can be walked over.
        ("transparent", bool),  # True if this tile doesn't block FOV.
        ("char", str),
        ("dark", graphic_dt),  # Graphics for when this tile is not in FOV.
        ("light", graphic_dt),  # Graphics for when the tile is in FOV.
    ]
)


def new_tile(
    *,  # Enforce the use of keywords, so that parameter order doesn't matter.
    walkable: int,
    transparent: int,
    char: str = "?", 
    dark: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
    light: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
) -> np.ndarray:
    """Helper function for defining individual tile types """
    return np.array((walkable, transparent, char, dark, light), dtype=tile_dt)


# SHROUD represents unexplored, unseen tiles
SHROUD = np.array((ord(" "), color.white, color.shroud_color), dtype=graphic_dt)

floor = new_tile(
    walkable=True,
    transparent=True,
    char=".",
    dark=(ord(" "), color.white, color.floor_colors[0]),
    light=(ord(" "), color.white, color.floor_colors[1]),
)
wall = new_tile(
    walkable=False,
    transparent=False,
    char="#",
    dark=(ord(" "), color.white, color.wall_colors[0]),
    light=(ord(" "), color.white,color.wall_colors[1]),
)
down_stairs = new_tile(
    walkable=True,
    transparent=True,
    char=">",
    dark=(ord(">"), color.down_stairs_colors_dark[0], color.down_stairs_colors_dark[1]),
    light=(ord(">"), color.down_stairs_colors_light[0], color.down_stairs_colors_light[1]),
)
