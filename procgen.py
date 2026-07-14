from __future__ import annotations

import random
from typing import Dict, Iterator, List, Tuple, TYPE_CHECKING
from collections import deque

import tcod #type: ignore

import entity_factories
from game_map import GameMap
import tile_types


if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


max_items_by_floor = [
    (1, 1),
    (4, 2),
]

max_monsters_by_floor = [
    (1, 2),
    (4, 3),
    (6, 5),
]

item_chances: Dict[int, List[Tuple[Entity, int]]] = {
    0: [(entity_factories.health_potion, 35)],
    2: [(entity_factories.confusion_scroll, 10)],
    4: [(entity_factories.lightning_scroll, 25), (entity_factories.sword, 5)],
    6: [(entity_factories.fireball_scroll, 25), (entity_factories.chain_mail, 15)],
}

enemy_chances: Dict[int, List[Tuple[Entity, int]]] = {
    0: [(entity_factories.orc, 80)],
    3: [(entity_factories.troll, 15)],
    5: [(entity_factories.troll, 30)],
    7: [(entity_factories.troll, 60)],
}


def get_max_value_for_floor(
    max_value_by_floor: List[Tuple[int, int]], floor: int
) -> int:
    current_value = 0

    for floor_minimum, value in max_value_by_floor:
        if floor_minimum > floor:
            break
        else:
            current_value = value

    return current_value


def get_entities_at_random(
    weighted_chances_by_floor: Dict[int, List[Tuple[Entity, int]]],
    number_of_entities: int,
    floor: int,
) -> List[Entity]:
    entity_weighted_chances = {}

    for key, values in weighted_chances_by_floor.items():
        if key > floor:
            break
        else:
            for value in values:
                entity = value[0]
                weighted_chance = value[1]

                entity_weighted_chances[entity] = weighted_chance

    entities = list(entity_weighted_chances.keys())
    entity_weighted_chance_values = list(entity_weighted_chances.values())

    chosen_entities = random.choices(
        entities, weights=entity_weighted_chance_values, k=number_of_entities
    )

    return chosen_entities


class RectangularRoom:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

    @property
    def center(self) -> Tuple[int, int]:
        center_x = int((self.x1 + self.x2) / 2)
        center_y = int((self.y1 + self.y2) / 2)

        return center_x, center_y

    @property
    def inner(self) -> Tuple[slice, slice]:
        """Return the inner area of this room as a 2D array index."""
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def intersects(self, other: RectangularRoom) -> bool:
        """Return True if this room overlaps with another RectangularRoom."""
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )


def place_entities(room: RectangularRoom, dungeon: GameMap, floor_number: int,) -> None:
    number_of_monsters = random.randint(
        0, get_max_value_for_floor(max_monsters_by_floor, floor_number)
    )
    number_of_items = random.randint(
        0, get_max_value_for_floor(max_items_by_floor, floor_number)
    )

    monsters: List[Entity] = get_entities_at_random(
        enemy_chances, number_of_monsters, floor_number
    )
    items: List[Entity] = get_entities_at_random(
        item_chances, number_of_items, floor_number
    )

    for entity in monsters + items:
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        if not any(entity.x == x and entity.y == y for entity in dungeon.entities):
            entity.spawn(dungeon, x, y)
            
def get_floor_tiles(cave):
    """Return a list of (x, y) floor coordinates."""
    tiles = []
    height = len(cave)
    width = len(cave[0])

    for y in range(height):
        for x in range(width):
            if cave[y][x] == 0:
                tiles.append((x, y))

    return tiles

def place_entities_in_cave(
    dungeon: GameMap,
    cave: List[List[int]],
    floor_number: int
) -> None:
    floor_tiles = get_floor_tiles(cave)

    number_of_monsters = random.randint(
        0, get_max_value_for_floor(max_monsters_by_floor, floor_number)
    )
    number_of_items = random.randint(
        0, get_max_value_for_floor(max_items_by_floor, floor_number)
    )

    monsters: List[Entity] = get_entities_at_random(
        enemy_chances, number_of_monsters, floor_number
    )
    items: List[Entity] = get_entities_at_random(
        item_chances, number_of_items, floor_number
    )

    # Shuffle floor tiles so we can pop from the front
    random.shuffle(floor_tiles)

    for entity in monsters + items:
        if not floor_tiles:
            break  # No valid tiles left

        x, y = floor_tiles.pop()

        # Ensure no entity already occupies this tile
        if not any(e.x == x and e.y == y for e in dungeon.entities):
            entity.spawn(dungeon, x, y)


def tunnel_between(
    start: Tuple[int, int], end: Tuple[int, int]
) -> Iterator[Tuple[int, int]]:
    """Return an L-shaped tunnel between these two points."""
    x1, y1 = start
    x2, y2 = end
    if random.random() < 0.5:  # 50% chance.
        # Move horizontally, then vertically.
        corner_x, corner_y = x2, y1
    else:
        # Move vertically, then horizontally.
        corner_x, corner_y = x1, y2

    # Generate the coordinates for this tunnel.
    for x, y in tcod.los.bresenham((x1, y1), (corner_x, corner_y)).tolist():
        yield x, y
    for x, y in tcod.los.bresenham((corner_x, corner_y), (x2, y2)).tolist():
        yield x, y

def generate_cave_dungeon(
    map_width: int,
    map_height: int,
    engine: Engine,
) -> GameMap:

    player = engine.player
    dungeon = GameMap(engine, map_width, map_height, entities=[player])

    # --- Generate cave + spawn point ---
    cave, (px, py) = generate_connected_cave(map_width, map_height, passes=6)

    # --- Apply cave tiles to dungeon ---
    for y in range(map_height):
        for x in range(map_width):
            dungeon.tiles[x, y] = (
                tile_types.wall if cave[y][x] == 1 else tile_types.floor
            )

    # --- Place player ---
    player.place(px, py, dungeon)

    # --- Place stairs ---
    floor_tiles = get_floor_tiles(cave)
    random.shuffle(floor_tiles)
    sx, sy = floor_tiles[0]
    dungeon.tiles[sx, sy] = tile_types.down_stairs
    dungeon.downstairs_location = (sx, sy) #type: ignore

    # --- Place monsters/items using your existing logic ---
    place_entities_in_cave(dungeon, cave, engine.game_world.current_floor)

    return dungeon

def generate_dungeon(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    engine: Engine,
) -> GameMap:
    """Generate a new dungeon map."""
    player = engine.player
    dungeon = GameMap(engine, map_width, map_height, entities=[player])

    rooms: List[RectangularRoom] = []

    center_of_last_room = (0, 0)

    for r in range(max_rooms):
        room_width = random.randint(room_min_size, room_max_size)
        room_height = random.randint(room_min_size, room_max_size)

        x = random.randint(0, dungeon.width - room_width - 1)
        y = random.randint(0, dungeon.height - room_height - 1)

        # "RectangularRoom" class makes rectangles easier to work with
        new_room = RectangularRoom(x, y, room_width, room_height)

        # Run through the other rooms and see if they intersect with this one.
        if any(new_room.intersects(other_room) for other_room in rooms):
            continue  # This room intersects, so go to the next attempt.
        # If there are no intersections then the room is valid.

        # Dig out this rooms inner area.
        dungeon.tiles[new_room.inner] = tile_types.floor

        if len(rooms) == 0:
            # The first room, where the player starts.
            player.place(*new_room.center, dungeon)
            """THIS IS ALL FOR TESTING"""
            cx, cy = new_room.center
            entity_factories.fireball_scroll.spawn(dungeon, cx, cy)
            entity_factories.confusion_scroll.spawn(dungeon, cx - 1, cy + 1)
            
        else:  # All rooms after the first.
            # Dig out a tunnel between this room and the previous one.
            for x, y in tunnel_between(rooms[-1].center, new_room.center):
                dungeon.tiles[x, y] = tile_types.floor

            center_of_last_room = new_room.center

        place_entities(new_room, dungeon, engine.game_world.current_floor)

        dungeon.tiles[center_of_last_room] = tile_types.down_stairs
        dungeon.downstairs_location = center_of_last_room #type: ignore

        # Finally, append the new room to the list.
        rooms.append(new_room)

    return dungeon

# ------------------------------------------------------------
# 1. Noise map generation
# ------------------------------------------------------------

def generate_noise_map(width: int, height: int, wall_prob: float = 0.45) -> List[List[int]]:
    """Return a 2D map filled with random walls/floors."""
    return [
        [1 if random.random() < wall_prob else 0 for _ in range(width)]
        for _ in range(height)
    ]

# ------------------------------------------------------------
# 2. Cellular automata smoothing
# ------------------------------------------------------------

def count_walls_around(map_data: List[List[int]], x: int, y: int) -> int:
    """Count walls in the 8 surrounding tiles."""
    count = 0
    for ny in range(y - 1, y + 2):
        for nx in range(x - 1, x + 2):
            if nx == x and ny == y:
                continue
            if nx < 0 or ny < 0 or ny >= len(map_data) or nx >= len(map_data[0]):
                count += 1  # Treat out-of-bounds as walls
            elif map_data[ny][nx] == 1:
                count += 1
    return count

def do_simulation_step(map_data: List[List[int]]) -> List[List[int]]:
    """Apply one CA smoothing pass."""
    width = len(map_data[0])
    height = len(map_data)
    new_map = [[0 for _ in range(width)] for _ in range(height)]

    for y in range(height):
        for x in range(width):
            walls = count_walls_around(map_data, x, y)

            if map_data[y][x] == 1:
                new_map[y][x] = 1 if walls >= 4 else 0
            else:
                new_map[y][x] = 1 if walls >= 5 else 0

    return new_map

# ------------------------------------------------------------
# 3. Flood-fill connectivity
# ------------------------------------------------------------

def flood_fill_reachable(cave: List[List[int]], start: Tuple[int, int]) -> List[List[bool]]:
    """Return a boolean map of reachable floor tiles."""
    width = len(cave[0])
    height = len(cave)

    reachable = [[False for _ in range(width)] for _ in range(height)]
    sx, sy = start

    if cave[sy][sx] == 1:
        return reachable  # Start is a wall — nothing reachable

    queue = deque([(sx, sy)])
    reachable[sy][sx] = True

    while queue:
        x, y = queue.popleft()

        for nx, ny in [(x+1,y), (x-1,y), (x,y+1), (x,y-1)]:
            if 0 <= nx < width and 0 <= ny < height:
                if cave[ny][nx] == 0 and not reachable[ny][nx]:
                    reachable[ny][nx] = True
                    queue.append((nx, ny))

    return reachable

def enforce_connectivity(cave: List[List[int]], start: Tuple[int, int]) -> List[List[int]]:
    """Convert unreachable floor tiles into walls."""
    reachable = flood_fill_reachable(cave, start)

    width = len(cave[0])
    height = len(cave)

    for y in range(height):
        for x in range(width):
            if cave[y][x] == 0 and not reachable[y][x]:
                cave[y][x] = 1  # Convert unreachable floor to wall

    return cave

# ------------------------------------------------------------
# 4. Full cave generation pipeline
# ------------------------------------------------------------

def generate_cave(width: int, height: int, passes: int = 6) -> List[List[int]]:
    """Generate a cave using cellular automata."""
    cave = generate_noise_map(width, height)

    for _ in range(passes):
        cave = do_simulation_step(cave)

    return cave

# ------------------------------------------------------------
# 5. Helper: find a valid spawn point
# ------------------------------------------------------------

def find_valid_spawn_point(cave: List[List[int]]) -> Tuple[int, int]:
    """Pick a random floor tile."""
    height = len(cave)
    width = len(cave[0])

    while True:
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        if cave[y][x] == 0:
            return x, y

# ------------------------------------------------------------
# 6. High-level: generate connected cave + spawn point
# ------------------------------------------------------------

def generate_connected_cave(width: int, height: int, passes: int = 6):
    """Generate a cave and enforce connectivity from the spawn point."""
    cave = generate_cave(width, height, passes)
    spawn = find_valid_spawn_point(cave)
    cave = enforce_connectivity(cave, spawn)
    return cave, spawn
