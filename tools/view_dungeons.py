import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tcod #type: random
import random

from engine import Engine
from game_map import GameMap
import tile_types
import entity_factories
from procgen import generate_cave_dungeon

def bg(r, g, b):
    return f"\x1b[48;2;{r};{g};{b}m"

RESET = "\x1b[0m"

COLORS = {
    "wall": bg(60, 60, 90),         # dark bluish
    "floor": bg(120, 120, 140),     # muted gray
    "door": bg(180, 140, 60),       # warm brown (future use)
    "stairs": bg(255, 255, 120),    # bright yellow

    "monster": bg(255, 80, 80),     # red
    "item": bg(80, 255, 80),        # green
    "player": bg(80, 200, 255),     # cyan
}

def print_legend():
    print("LEGEND:")
    print(COLORS["wall"]   + "  " + RESET + " = Wall")
    print(COLORS["floor"]  + "  " + RESET + " = Floor")
    print(COLORS["door"]   + "  " + RESET + " = Door")
    print(COLORS["stairs"] + "  " + RESET + " = Down Stairs")
    print(COLORS["monster"]+ "  " + RESET + " = Monster")
    print(COLORS["item"]   + "  " + RESET + " = Item")
    print(COLORS["player"] + "  " + RESET + " = Player")
    print()


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
    print_legend()

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
                # Player
                if entity_here is dungeon.engine.player:
                    row += COLORS["player"] + "  " + RESET
                    continue

                # Monster (Actor)
                if hasattr(entity_here, "fighter"):
                    row += COLORS["monster"] + "  " + RESET
                    continue

                # Item
                row += COLORS["item"] + "  " + RESET
                continue

            # Tiles
            tile = dungeon.tiles[x, y]

            if tile == tile_types.wall:
                row += COLORS["wall"] + "  " + RESET
            elif tile == tile_types.floor:
                row += COLORS["floor"] + "  " + RESET
            elif tile == tile_types.down_stairs:
                row += COLORS["stairs"] + "  " + RESET
            else:
                row += bg(0, 0, 0) + "  " + RESET  # unknown tile

        lines.append(row)

    print("\n".join(lines))



# --- Fake engine for testing ---
class DummyEngine(Engine):
    def __init__(self):
        # Create a fake player entity
        self.player = entity_factories.player
        self.game_world = type("GW", (), {"current_floor": 1}) #type: ignore


# --- Main test harness ---
def main():
    engine = DummyEngine()

    for i in range(20):
        print(f"\n=== DUNGEON {i+1} ===\n")
        dungeon = generate_cave_dungeon(
            map_width=80,
            map_height=45,
            engine=engine
        )
        print_dungeon(dungeon)


if __name__ == "__main__":
    main()
