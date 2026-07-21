# character_builder.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class CharacterBuilder:
    """Holds temporary choices during character creation."""
    race_id: Optional[str] = None
    subrace_id: Optional[str] = None
    class_id: Optional[str] = None
    stats: Dict[str, int] = field(default_factory=dict)
    starting_location: Optional[str] = None
