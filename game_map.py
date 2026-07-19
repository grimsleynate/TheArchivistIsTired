from __future__ import annotations

from typing import Iterable, Iterator, Optional, TYPE_CHECKING, Dict, Tuple, List

import numpy as np  # type: ignore
from tcod.console import Console  # type: ignore

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
        # Tile items are stored as stacks: List[List[Item]]
        self.items_at_location: Dict[Tuple[int, int], List[List[Item]]] = {}
        self.tiles = np.full((width, height), fill_value=tile_types.wall, order="F")

        self.visible = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player can currently see
        self.explored = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player has seen before

    @property
    def gamemap(self) -> "GameMap":
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
        """Iterate over item entities (if kept in entities)."""
        yield from (entity for entity in self.entities if isinstance(entity, Item))

    def get_blocking_entity_at_location(
        self, location_x: int, location_y: int,
    ) -> Optional["Entity"]:
        for entity in self.entities:
            if (
                entity.blocks_movement
                and entity.x == location_x
                and entity.y == location_y
            ):
                return entity
        return None

    def get_items_at(self, x: int, y: int) -> List[List[Item]]:
        """Return stacks of items at a tile."""
        return self.items_at_location.get((x, y), [])

    def add_item(self, item: Item, x: int, y: int) -> None:
        """Add an item to a tile, stacking with like items."""
        stacks = self.items_at_location.setdefault((x, y), [])

        # Ensure parent is this map
        item.parent = self

        # Try to merge into existing stack
        for stack in stacks:
            if stack and stack[0].name == item.name and len(stack) < stack[0].max_stack:
                stack.append(item)
                return

        # Otherwise create new stack
        stacks.append([item])

    def remove_item(self, item: Item, x: int, y: int) -> None:
        """Remove an item from tile stacks at (x, y)."""
        if (x, y) not in self.items_at_location:
            return

        stacks = self.items_at_location[(x, y)]
        if not stacks:
            return

        for stack in stacks:
            if item in stack:
                stack.remove(item)
                if not stack:
                    stacks.remove(stack)
                break

        if not stacks:
            del self.items_at_location[(x, y)]

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
            choicelist=[
                self.tiles["light"][cam_x:cam_x+view_w, cam_y:cam_y+view_h],
                self.tiles["dark"][cam_x:cam_x+view_w, cam_y:cam_y+view_h],
            ],
            default=tile_types.SHROUD,
        )

        # Blit into console (top-left aligned)
        console.tiles_rgb[0:view_w, 0:view_h] = tile_slice

        # Render entities in viewport
        for entity in sorted(self.entities, key=lambda x: x.render_order.value):
            ex, ey = entity.x, entity.y

            # Skip entities outside visibility or viewport
            if not self.visible[ex, ey]:
                continue
            if not (cam_x <= ex < cam_x + view_w and cam_y <= ey < cam_y + view_h):
                continue

            # --- MULTI-ITEM TILE OVERRIDE ---
            stacks_here = self.get_items_at(ex, ey)
            total_items = sum(len(stack) for stack in stacks_here)

            # If this tile has multiple items, draw the special glyph ONCE
            if total_items > 1:
                console.print(
                    x=ex - cam_x,
                    y=ey - cam_y,
                    string="‼",
                    fg=(80, 255, 80),
                    bg=(120, 120, 140),
                )
                # Skip drawing item entities on this tile
                if isinstance(entity, Item):
                    continue

            # If this tile has exactly one item, draw that item instead of the entity
            elif total_items == 1 and isinstance(entity, Item):
                # Find the single item
                item: Optional[Item] = None
                for stack in stacks_here:
                    if stack:
                        item = stack[0]
                        break

                if item:
                    console.print(
                        x=ex - cam_x,
                        y=ey - cam_y,
                        string=item.char,
                        fg=item.color,
                    )
                    continue

            # --- DEFAULT ENTITY RENDERING ---
            console.print(
                x=ex - cam_x,
                y=ey - cam_y,
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
        from procgen import generate_dungeon, generate_cave_dungeon

        self.current_floor += 1

        self.engine.game_map = generate_cave_dungeon(
            map_width=self.map_width,
            map_height=self.map_height,
            engine=self.engine,
        )
