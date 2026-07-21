from __future__ import annotations

import copy
import math
from typing import Dict, Optional, Set, Tuple, Type, TypeVar, TYPE_CHECKING, Union

from render_order import RenderOrder

if TYPE_CHECKING:
    from components.ai import BaseAI
    from components.consumable import Consumable
    from components.equipment import Equipment
    from components.equippable import Equippable
    from components.fighter import Fighter
    from components.inventory import Inventory
    from components.level import Level
    from game_map import GameMap
    from entity import Item

T = TypeVar("T", bound="Entity")


class Entity:
    """
    A generic object to represent players, enemies, items, etc.
    """

    parent: Union[GameMap, Inventory]

    def __init__(
        self,
        parent: Optional[GameMap] = None,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        max_stack: int = 1,
        blocks_movement: bool = False,
        render_order: RenderOrder = RenderOrder.CORPSE,
    ):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.tags: set[str] = set()
        self.blocks_movement = blocks_movement
        self.render_order = render_order
        self.max_stack = max_stack
        self.stack_size = 1
        if parent:
            # If parent isn't provided now then it will be set later.
            self.parent = parent
            parent.entities.add(self)

    @property
    def gamemap(self) -> Optional["GameMap"]:
        """Return the GameMap this entity belongs to, if any."""
        if self.parent is None:
            return None
        # If parent is a GameMap, return it directly
        from game_map import GameMap
        if isinstance(self.parent, GameMap):
            return self.parent
        # If parent is something like Inventory, delegate
        if hasattr(self.parent, "gamemap"):
            return self.parent.gamemap
        return None

    @gamemap.setter
    def gamemap(self, value: Optional["GameMap"]):
        # Accept either a GameMap instance or None
        self.parent = value

    def spawn(self: T, gamemap: GameMap, x: int, y: int) -> T:
        """Spawn a copy of this instance at the given location."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = gamemap
        gamemap.entities.add(clone)
        
        if isinstance(clone, Item):
            gamemap.add_item(clone, x, y)
            
        return clone

    def place(self, x: int, y: int, gamemap):
        # Remove from old gamemap if present
        if getattr(self, "gamemap", None) is not None:
            try:
                self.gamemap.entities.remove(self)
            except Exception:
                pass

        # Update coordinates and gamemap
        self.x = x
        self.y = y
        self.gamemap = gamemap

        # Add to new gamemap if provided
        if gamemap is not None:
            gamemap.entities.add(self)


    def distance(self, x: int, y: int) -> float:
        """
        Return the distance between the current entity and the given (x, y) coordinate.
        """
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def move(self, dx: int, dy: int) -> None:
        # Move the entity by a given amount
        self.x += dx
        self.y += dy
        
    # Tag helpers (available on all Entities)
    def add_tag(self, tag: str) -> None:
        self.tags.add(tag)

    def remove_tag(self, tag: str) -> None:
        self.tags.discard(tag)

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags



class Actor(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        max_stack: int = 1,
        ai_cls: Type[BaseAI],
        equipment: Equipment,
        fighter: Fighter,
        inventory: Inventory,
        level: Level,
    ):
        super().__init__(
            x=x,
            y=y,
            char=char,
            color=color,
            name=name,
            max_stack=max_stack,
            blocks_movement=True,
            render_order=RenderOrder.ACTOR,
        )

        # AI may be optional in some templates
        self.ai: Optional[BaseAI] = ai_cls(self) if ai_cls is not None else None

        # Components may be missing in malformed data; attach only if present
        self.equipment: Optional[Equipment] = equipment
        if self.equipment is not None:
            self.equipment.parent = self

        self.fighter: Optional[Fighter] = fighter
        if self.fighter is not None:
            self.fighter.parent = self

        self.inventory: Optional[Inventory] = inventory
        if self.inventory is not None:
            self.inventory.parent = self

        self.level: Optional[Level] = level
        if self.level is not None:
            self.level.parent = self

        self.race_id: Optional[str] = None
        self.subrace_id: Optional[str] = None
        
        self.base_attributes: Dict[str, int] = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        
        self.tags: Set[str] = set()

    @property
    def is_alive(self) -> bool:
        """Returns True as long as this actor can perform actions."""
        return bool(self.ai)
    
    def add_tag(self, tag: str) -> None:
        self.tags.add(tag)

    def remove_tag(self, tag: str) -> None:
        self.tags.discard(tag)

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def apply_attribute_modifiers(self, modifiers: Dict[str, int]) -> None:
        """
        Add modifiers into base_attributes (used at creation to apply race/subrace).
        This mutates base_attributes so future calculations use the merged values.
        """
        for k, v in modifiers.items():
            self.base_attributes[k] = self.base_attributes.get(k, 0) + int(v)

    def get_effective_attribute(self, key: str) -> int:
        """Return the current effective attribute (base + any other sources if you add them later)."""
        return self.base_attributes.get(key, 0)


class Item(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        max_stack: int = 1,
        description: str = "",
        consumable: Optional[Consumable] = None,
        equippable: Optional[Equippable] = None,
    ):
        super().__init__(
            x=x,
            y=y,
            char=char,
            color=color,
            name=name,
            max_stack=max_stack,
            blocks_movement=False,
            render_order=RenderOrder.ITEM,
        )

        self.consumable = consumable

        if self.consumable:
            self.consumable.parent = self

        self.equippable = equippable

        if self.equippable:
            self.equippable.parent = self
