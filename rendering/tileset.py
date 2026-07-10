# render/tileset.py
import pygame

class TileSet:
    def __init__(self, image_path: str, tile_size: int):
        self.image = pygame.image.load(image_path).convert_alpha()
        self.tile_size = tile_size
        self.columns = max(1, self.image.get_width() // tile_size)
        self.rows = max(1, self.image.get_height() // tile_size)
        self._cache = []
        for ty in range(self.rows):
            for tx in range(self.columns):
                rect = pygame.Rect(tx * tile_size, ty * tile_size, tile_size, tile_size)
                surf = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                surf.blit(self.image, (0, 0), rect)
                self._cache.append(surf)

    def get_tile(self, index: int):
        if index is None:
            return pygame.Surface((self.tile_size, self.tile_size), pygame.SRCALPHA)
        if index < 0 or index >= len(self._cache):
            return pygame.Surface((self.tile_size, self.tile_size), pygame.SRCALPHA)
        return self._cache[index]
