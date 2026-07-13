import json
import random
from pathlib import Path

import tile_types
from game_map import GameMap
import entity_factories


def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def choose_from_pool(pool: list[dict], count: int):
    entities = [getattr(entity_factories, c["id"]) for c in pool]
    weights = [c["weight"] for c in pool]
    return random.choices(entities, weights=weights, k=count)


def load_map(engine, txt_path: str, json_path: str, item_pool_path="pools/item_pools.json", monster_pool_path="pools/monster_pools.json") -> GameMap:
    # Load ASCII layout
    with open(txt_path, "r") as f:
        ascii_map = [list(line.rstrip("\n")) for line in f]

    metadata = load_json(json_path)
    item_pools = load_json(item_pool_path)
    monster_pools = load_json(monster_pool_path)

    height = len(ascii_map)
    width = len(ascii_map[0])

    dungeon = GameMap(engine, width, height, entities=[engine.player])
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

    # Spawn items from pools
    for pool_def in metadata.get("item_pools", []):
        pool_id = pool_def["pool_id"]
        count = pool_def.get("count", 1)
        chosen_items = choose_from_pool(item_pools[pool_id], count)
        for item in chosen_items:
            while True:
                x = random.randint(1, width - 2)
                y = random.randint(1, height - 2)
                if dungeon.tiles[x, y] == tile_types.floor:
                    item.spawn(dungeon, x, y)
                    break

    # Spawn direct items
    for item_def in metadata.get("items", []):
        item = getattr(entity_factories, item_def["id"])
        item.spawn(dungeon, item_def["x"], item_def["y"])

    # Spawn monsters from pools
    for pool_def in metadata.get("monster_pools", []):
        pool_id = pool_def["pool_id"]
        count = pool_def.get("count", 1)
        chosen_monsters = choose_from_pool(monster_pools[pool_id], count)
        for monster in chosen_monsters:
            while True:
                x = random.randint(1, width - 2)
                y = random.randint(1, height - 2)
                if dungeon.tiles[x, y] == tile_types.floor:
                    monster.spawn(dungeon, x, y)
                    break

    return dungeon
