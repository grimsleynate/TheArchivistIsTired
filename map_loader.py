import json
import random
from pathlib import Path

import tile_types
from game_map import GameMap

def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)

def choose_from_pool(factory, pool: list[dict], count: int):
    """
    pool entries look like:
    { "id": "item.health_potion", "weight": 10 }
    or
    { "id": "actor.orc", "weight": 12 }
    """
    ids = [entry["id"] for entry in pool]
    weights = [entry["weight"] for entry in pool]
    chosen_ids = random.choices(ids, weights=weights, k=count)
    return [factory.create_item(i) if i.startswith("item.")
            else factory.create_actor(i)
            for i in chosen_ids]

def load_map(
    engine,
    txt_path: str,
    json_path: str,
    item_pool_path="pools/item_pools.json",
    monster_pool_path="pools/monster_pools.json"
) -> GameMap:

    # Load ASCII layout
    with open(txt_path, "r") as f:
        ascii_map = [list(line.rstrip("\n")) for line in f]

    metadata = load_json(json_path)
    item_pools = load_json(item_pool_path)
    monster_pools = load_json(monster_pool_path)

    height = len(ascii_map)
    width = len(ascii_map[0])

    dungeon = GameMap(engine, width, height, entities=[engine.player])
    
    # Ensure engine.player exists and is placeable
    if getattr(engine, "player", None) is None:
        # Try to create a player from the factory if available
        if getattr(engine, "factory", None):
            print("load_map: engine.player is None — creating default player via factory.create_actor('actor.player')")
            engine.player = engine.factory.create_actor("actor.player")
        else:
            raise RuntimeError("load_map: engine.player is None and no engine.factory available to create one")

    if not hasattr(engine.player, "place"):
        print("load_map: engine.player exists but has no place() method:", repr(engine.player))
        raise RuntimeError("load_map: engine.player missing place()")
    # Defensive check: ensure engine.player exists and has place
    if getattr(engine, "player", None) is None:
        print("ERROR: engine.player is None in load_map()")
        raise RuntimeError("load_map: engine.player is None; cannot place player on map")
    if not hasattr(engine.player, "place"):
        print("ERROR: engine.player has no 'place' method. engine.player:", repr(engine.player))
        raise RuntimeError("load_map: engine.player missing place()")
    
    engine.player.place(1, 1, dungeon)

    # Fill tiles
    for y, row in enumerate(ascii_map):
        for x, char in enumerate(row):
            if char == "#":
                dungeon.tiles[x, y] = tile_types.wall
            elif char == ".":
                dungeon.tiles[x, y] = tile_types.floor
            elif char == ">":
                dungeon.tiles[x, y] = tile_types.down_stairs

    factory = engine.factory

    # Spawn items from pools
    for pool_def in metadata.get("item_pools", []):
        pool_id = pool_def["pool_id"]
        count = pool_def.get("count", 1)

        chosen_items = choose_from_pool(factory, item_pools[pool_id], count)

        for item in chosen_items:
            if item is None:
                print("ERROR: choose_from_pool returned None for an item in pool", pool_id)
                raise RuntimeError(f"load_map: factory returned None for item in pool {pool_id}")
            if not hasattr(item, "place"):
                print("ERROR: created item has no place():", repr(item))
                raise RuntimeError("load_map: created item missing place()")

            while True:
                x = random.randint(1, width - 2)
                y = random.randint(1, height - 2)
                if dungeon.tiles[x, y] == tile_types.floor:
                    item.place(x, y, dungeon)
                    dungeon.add_item(item, x, y)
                    break

    # Spawn direct items
    for item_def in metadata.get("items", []):
        item = factory.create_item(item_def["id"])
        if item is None:
            print("ERROR: factory.create_item returned None for id:", item_def["id"])
            raise RuntimeError(f"load_map: create_item returned None for {item_def['id']}")
        if not hasattr(item, "place"):
            print("ERROR: created item has no place():", repr(item))
            raise RuntimeError("load_map: created item missing place()")

        item.place(item_def["x"], item_def["y"], dungeon)
        dungeon.add_item(item, item_def["x"], item_def["y"])


    # Spawn monsters from pools
    for pool_def in metadata.get("monster_pools", []):
        pool_id = pool_def["pool_id"]
        count = pool_def.get("count", 1)

        chosen_monsters = choose_from_pool(factory, monster_pools[pool_id], count)

        for monster in chosen_monsters:
            if monster is None:
                print("ERROR: choose_from_pool returned None for a monster in pool", pool_id)
                raise RuntimeError(f"load_map: factory returned None for monster in pool {pool_id}")
            if not hasattr(monster, "place"):
                print("ERROR: created monster has no place():", repr(monster))
                raise RuntimeError("load_map: created monster missing place()")

            while True:
                x = random.randint(1, width - 2)
                y = random.randint(1, height - 2)
                if dungeon.tiles[x, y] == tile_types.floor:
                    dungeon.entities.add(monster)
                    monster.place(x, y, dungeon)
                    break

    return dungeon
