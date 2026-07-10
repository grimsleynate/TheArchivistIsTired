# render/tileset_manager.py
from typing import Dict, Optional
from .tileset import TileSet

class TileSetManager:
    def __init__(self):
        self._sets: Dict[str, TileSet] = {}

    def load(self, name: str, path: str, tile_size: int) -> None:
        if name in self._sets:
            return
        self._sets[name] = TileSet(path, tile_size)

    def get(self, name: str) -> Optional[TileSet]:
        return self._sets.get(name)

    def has(self, name: str) -> bool:
        return name in self._sets
