import json
from pathlib import Path
from typing import Dict

class TagRepository:
    def __init__(self, path: str = "data/tags.json"):
        self.path = Path(path)
        self.tags: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for entry in data.get("tags", []):
            tid = entry.get("id")
            if not tid:
                continue
            self.tags[tid] = {
                "id": tid,
                "name": entry.get("name", tid),
                "description": entry.get("description", "")
            }

    def get(self, tag_id: str):
        return self.tags.get(tag_id)

    def all(self):
        return dict(self.tags)
