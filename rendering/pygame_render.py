# render/pygame_render.py
import pygame
from typing import Any
from .tileset_manager import TileSetManager
from .render_component import RenderComponent

_FONT = None

def _init_font(tile_size: int):
    global _FONT
    if _FONT is None:
        try:
            _FONT = pygame.font.SysFont("Consolas", tile_size)
        except Exception:
            _FONT = pygame.font.SysFont("monospace", tile_size)

def render_all(engine: Any) -> None:
    """
    Minimal Pygame renderer used only for TILE mode.
    It reads engine.game_map and entity render_component or legacy fields.
    """
    screen = getattr(engine, "screen", None)
    if screen is None:
        return

    tile_size = getattr(engine, "tile_size", 16)
    _init_font(tile_size)

    screen.fill((0, 0, 0))

    game_map = engine.game_map
    manager: TileSetManager = getattr(engine, "tileset_manager", None)

    def get_tile_obj(x, y):
        tiles = getattr(game_map, "tiles", None)
        if tiles is None:
            return None
        try:
            return tiles[x][y]
        except Exception:
            try:
                return tiles[x, y]
            except Exception:
                return None

    # draw map
    for x in range(game_map.width):
        for y in range(game_map.height):
            tile = get_tile_obj(x, y)
            if tile is None:
                continue
            tileset_name = getattr(tile, "tileset_name", "tiles")
            tile_index = getattr(tile, "tile_index", None)
            if manager and manager.has(tileset_name):
                ts = manager.get(tileset_name)
                surf = ts.get_tile(tile_index)
                screen.blit(surf, (x * tile_size, y * tile_size))
            else:
                bg = getattr(tile, "bg", (0,0,0))
                fg = getattr(tile, "fg", (255,255,255))
                rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
                pygame.draw.rect(screen, bg, rect)
                ch = getattr(tile, "char", "?")
                surf = _FONT.render(ch, True, fg)
                screen.blit(surf, rect.topleft)

    # draw entities
    entities = getattr(game_map, "entities", None) or getattr(engine, "entities", None) or []
    def zkey(e):
        rc = getattr(e, "render_component", None) or getattr(e, "render", None)
        if rc is not None:
            return getattr(rc, "z", 0)
        return getattr(e, "render_order", 0)

    for entity in sorted(entities, key=zkey):
        rc = getattr(entity, "render_component", None) or getattr(entity, "render", None)
        if rc is None:
            char = getattr(entity, "char", '?')
            color = getattr(entity, "color", (255,255,255))
            tileset_name = getattr(entity, "tileset_name", None)
            tile_index = getattr(entity, "tile_index", None)
        else:
            char = getattr(rc, "char", '?')
            color = getattr(rc, "color", (255,255,255))
            tileset_name = getattr(rc, "tileset", None)
            tile_index = getattr(rc, "tile_index", None)

        if tileset_name and manager and manager.has(tileset_name):
            ts = manager.get(tileset_name)
            surf = ts.get_tile(tile_index)
            screen.blit(surf, (entity.x * tile_size, entity.y * tile_size))
        else:
            rect = pygame.Rect(entity.x * tile_size, entity.y * tile_size, tile_size, tile_size)
            surf = _FONT.render(char, True, color)
            screen.blit(surf, rect.topleft)

    pygame.display.flip()
