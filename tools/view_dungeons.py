import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tcod
import random

from engine import Engine
from game_map import GameMap
import tile_types
import entity_factories
from procgen import generate_dungeon  # your file

# --- ASCII conversion helpers ---

def tile_to_char(tile):
    if tile == tile_types.wall:
        return "#"
    elif tile == tile_types.floor:
        return "."
    elif tile == tile_types.down_stairs:
        return ">"
    return "?"

def print_dungeon(dungeon: GameMap):
    lines = []
    for y in range(dungeon.height):
        row = ""
        for x in range(dungeon.width):

            # Check for entity
            entity_here = None
            for e in dungeon.entities:
                if e.x == x and e.y == y:
                    entity_here = e
                    break

            if entity_here:
                row += entity_here.char
            else:
                row += tile_to_char(dungeon.tiles[x, y])

        lines.append(row)

    print("\n".join(lines))


# --- Fake engine for testing ---
class DummyEngine(Engine):
    def __init__(self):
        # Create a fake player entity
        self.player = entity_factories.player
        self.game_world = type("GW", (), {"current_floor": 1})


# --- Main test harness ---
def main():
    engine = DummyEngine()

    for i in range(20):
        print(f"\n=== DUNGEON {i+1} ===\n")
        dungeon = generate_dungeon(
            max_rooms=30,
            room_min_size=6,
            room_max_size=10,
            map_width=80,
            map_height=45,
            engine=engine
        )
        print_dungeon(dungeon)


if __name__ == "__main__":
    main()
