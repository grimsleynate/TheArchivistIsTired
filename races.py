# races.py
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class Subrace:
    id: str
    name: str
    description: str = ""
    attributes: Dict[str, int] = field(default_factory=dict)
    starting_equipment: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)

@dataclass
class Race:
    id: str
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    attributes: Dict[str, int] = field(default_factory=dict)
    starting_equipment: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)
    subraces: List[Subrace] = field(default_factory=list)

def load_race_file(path: str) -> Race:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    subraces = []
    for s in data.get("subraces", []):
        subraces.append(Subrace(
            id=s["id"],
            name=s["name"],
            description=s.get("description", ""),
            attributes=s.get("attributes", {}),
            starting_equipment=s.get("starting_equipment", []),
            abilities=s.get("abilities", []),
        ))
    return Race(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        tags=data.get("tags", []),
        attributes=data.get("attributes", {}),
        starting_equipment=data.get("starting_equipment", []),
        abilities=data.get("abilities", []),
        subraces=subraces,
    )

def load_all_races(folder: str = "data/races") -> Dict[str, Race]:
    races = {}
    if not os.path.isdir(folder):
        return races
    for fname in os.listdir(folder):
        if fname.endswith(".json"):
            path = os.path.join(folder, fname)
            try:
                race = load_race_file(path)
                races[race.id] = race
            except Exception:
                # optionally log the error
                continue
    return races
