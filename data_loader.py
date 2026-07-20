import json
from pathlib import Path

class DataRepository:
    def __init__(self, actors_dir: str, items_dir: str):
        self.actor_defs = {}
        self.item_defs = {}

        self._load_dir(actors_dir, self.actor_defs)
        self._load_dir(items_dir, self.item_defs)

    def _load_dir(self, directory: str, target: dict):
        base = Path(directory)
        for p in base.rglob("*.json"):
            data = json.loads(p.read_text())
            target[data["id"]] = data

    def get_actor(self, actor_id: str):
        return self.actor_defs[actor_id]

    def get_item(self, item_id: str):
        return self.item_defs[item_id]
