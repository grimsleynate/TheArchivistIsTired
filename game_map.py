from __future__ import annotations

from typing import Iterable, Iterator, Optional, TYPE_CHECKING

import numpy as np  # type: ignore
from tcod.console import Console

from entity import Actor, Item
import tile_types

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


class GameMap:
    def __init__(
        self, engine: Engine, width: int, height: int, entities: Iterable[Entity] = ()
    ):
        self.engine = engine
        self.width, self.height = width, height
        self.entities = set(entities)
        self.tiles = np.full((width, height), fill_value=tile_types.wall, order="F")

        self.visible = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player can currently see
        self.explored = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player has seen before

        self.downstairs_location = (0, 0)

    @property
    def gamemap(self) -> GameMap:
        return self

    @property
    def actors(self) -> Iterator[Actor]:
        """Iterate over this maps living actors."""
        yield from (
            entity
            for entity in self.entities
            if isinstance(entity, Actor) and entity.is_alive
        )

    @property
    def items(self) -> Iterator[Item]:
        yield from (entity for entity in self.entities if isinstance(entity, Item))

    def get_blocking_entity_at_location(
        self, location_x: int, location_y: int,
    ) -> Optional[Entity]:
        for entity in self.entities:
            if (
                entity.blocks_movement
                and entity.x == location_x
                and entity.y == location_y
            ):
                return entity

        return None

    def get_actor_at_location(self, x: int, y: int) -> Optional[Actor]:
        for actor in self.actors:
            if actor.x == x and actor.y == y:
                return actor

        return None

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y < self.height

    def render(self, console: Console) -> None:
    # Camera centered on player
        cam_x = max(0, self.engine.player.x - console.width // 2)
        cam_y = max(0, self.engine.player.y - console.height // 2)

        # Clamp so we don’t go past map edges
        cam_x = min(cam_x, max(0, self.width - console.width))
        cam_y = min(cam_y, max(0, self.height - console.height))

        # Compute viewport size
        view_w = min(console.width, self.width)
        view_h = min(console.height, self.height)

        # Slice arrays
        visible_slice = self.visible[cam_x:cam_x+view_w, cam_y:cam_y+view_h]
        explored_slice = self.explored[cam_x:cam_x+view_w, cam_y:cam_y+view_h]

        tile_slice = np.select(
            condlist=[visible_slice, explored_slice],
            choicelist=[self.tiles["light"][cam_x:cam_x+view_w, cam_y:cam_y+view_h],
                        self.tiles["dark"][cam_x:cam_x+view_w, cam_y:cam_y+view_h]],
            default=tile_types.SHROUD,
        )

        # Blit into console (top-left aligned)
        console.tiles_rgb[0:view_w, 0:view_h] = tile_slice

        # Render entities in viewport
        for entity in sorted(self.entities, key=lambda x: x.render_order.value):
            if self.visible[entity.x, entity.y]:
                if cam_x <= entity.x < cam_x + view_w and cam_y <= entity.y < cam_y + view_h:
                    console.print(
                        x=entity.x - cam_x,
                        y=entity.y - cam_y,
                        string=entity.char,
                        fg=entity.color,
                    )



class GameWorld:
    """
    Holds the settings for the GameMap, and generates new maps when moving down the stairs.
    """

    def __init__(
        self,
        *,
        engine: Engine,
        map_width: int,
        map_height: int,
        max_rooms: int,
        room_min_size: int,
        room_max_size: int,
        current_floor: int = 0
    ):
        self.engine = engine

        self.map_width = map_width
        self.map_height = map_height

        self.max_rooms = max_rooms

        self.room_min_size = room_min_size
        self.room_max_size = room_max_size

        self.current_floor = current_floor

    def generate_floor(self) -> None:
        from procgen import generate_dungeon

        self.current_floor += 1

        self.engine.game_map = generate_dungeon(
            max_rooms=self.max_rooms,
            room_min_size=self.room_min_size,
            room_max_size=self.room_max_size,
            map_width=self.map_width,
            map_height=self.map_height,
            engine=self.engine,
        )
