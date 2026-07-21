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
            # Skip schema files (e.g., items.schema.json, races.schema.json)
            if p.name.endswith(".schema.json") or ".schema." in p.name:
                continue

            try:
                text = p.read_text()
            except Exception as e:
                raise RuntimeError(f"Failed to read {p}: {e}")

            try:
                data = json.loads(text)
            except Exception as e:
                raise RuntimeError(f"Failed to parse JSON in {p}: {e}")

            if not isinstance(data, dict):
                raise RuntimeError(f"Unexpected JSON root type in {p}: expected object with 'id'")

            if "id" not in data:
                raise RuntimeError(f"Missing required 'id' field in {p}")

            target[data["id"]] = data

    def get_actor(self, actor_id: str):
        return self.actor_defs[actor_id]

    def get_item(self, item_id: str):
        return self.item_defs[item_id]
