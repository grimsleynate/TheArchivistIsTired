# render/render_component.py
from typing import Tuple, Optional

class RenderComponent:
    def __init__(self,
                 char: str = '?',
                 color: Tuple[int,int,int] = (255,255,255),
                 tileset: Optional[str] = None,
                 tile_index: Optional[int] = None,
                 z: int = 0):
        self.char = char
        self.color = color
        self.tileset = tileset
        self.tile_index = tile_index
        self.z = z
