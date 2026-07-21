# components/equipment.py
from __future__ import annotations

from typing import Optional, TYPE_CHECKING, List, Dict, Any, Set

from components.base_component import BaseComponent
# Import canonical slot names and helpers from equipment_slots.py
from equipment_slots import (
    MAIN_HAND,
    OFF_HAND,
    HEAD,
    BODY,
    BACK,
    NECK,
    RING_ONE,
    RING_TWO,
    FEET,
    HANDS,
    normalize_slot_entry,
)

if TYPE_CHECKING:
    from entity import Actor, Item


class Equipment(BaseComponent):
    """
    Equipment component that maps canonical slot names -> equipped Item (or None).
    Designed to be extensible via equipment_slots.py.
    """

    parent: "Actor"

    def __init__(self, slots: Optional[List[str]] = None):
        # Default slot set; import names from equipment_slots so you can extend that file later
        default_slots = [
            MAIN_HAND,
            OFF_HAND,
            HEAD,
            BODY,
            BACK,
            NECK,
            RING_ONE,
            RING_TWO,
            FEET,
            HANDS,
        ]
        self.slot_names: List[str] = slots or default_slots
        # slot_name -> item (or None)
        self.slots: Dict[str, Optional["Item"]] = {s: None for s in self.slot_names}

    # --- Introspection helpers ------------------------------------------------

    def item_is_equipped(self, item: "Item") -> bool:
        """Return True if the given item is currently equipped in any slot."""
        return any(cur is item for cur in self.slots.values())

    def get_slots_for_item(self, item: "Item") -> List[str]:
        """Return a list of slot names the item currently occupies (empty list if not equipped)."""
        return [s for s, cur in self.slots.items() if cur is item]

    def get_equipped_in_slot(self, slot: str) -> Optional["Item"]:
        """Return the item equipped in the named slot, or None."""
        return self.slots.get(slot)

    def is_slot_free(self, slot: str) -> bool:
        """True if the named slot exists and is not occupied."""
        return self.slots.get(slot) is None

    # --- Stat aggregation helpers ---------------------------------------------

    @property
    def defense_bonus(self) -> int:
        bonus = 0
        for cur in set(self.slots.values()):
            if cur is not None and getattr(cur, "equippable", None) is not None:
                bonus += int(cur.equippable.defense_bonus or 0)
        return bonus

    @property
    def power_bonus(self) -> int:
        bonus = 0
        for cur in set(self.slots.values()):
            if cur is not None and getattr(cur, "equippable", None) is not None:
                bonus += int(cur.equippable.power_bonus or 0)
        return bonus

    # --- Capability checks ----------------------------------------------------

    def can_equip(self, item: "Item") -> bool:
        """
        Return True if this Equipment has the necessary slots to equip the item.
        Equippable component should expose required_slots() and allowed_slot_options().
        """
        eq = getattr(item, "equippable", None)
        if not eq:
            return False

        # If item requires specific slots, ensure those slots exist on this equipment
        req = getattr(eq, "occupies_slots", lambda: [])()
        if req:
            return all(s in self.slots for s in req)

        # Otherwise ensure at least one allowed slot exists on this equipment
        for s in getattr(eq, "allowed_slot_options", lambda: [])():
            if s in self.slots:
                return True

        return False

    # --- Equip / unequip logic -----------------------------------------------

    def equip(self, item: "Item", actor: Optional["Actor"] = None, add_message: bool = True) -> bool:
        """
        Equip an item. Returns True on success, False on failure.
        Behavior:
          - If item has required_slots (occupies_slots), occupy them (unequip conflicts first).
          - Else, pick a preferred free allowed slot (main_hand then off_hand), or auto-unequip occupant.
        """
        eq = getattr(item, "equippable", None)
        if not eq:
            return False

        # Items that occupy multiple slots (two-handers)
        req: List[str] = getattr(eq, "occupies_slots", lambda: [])() or []
        if req:
            # ensure all required slots exist
            for s in req:
                if s not in self.slots:
                    return False
            # unequip any items occupying those slots (collect unique items)
            to_unequip: Set[Optional["Item"]] = {self.slots[s] for s in req if self.slots[s] and self.slots[s] is not item}
            for cur in list(to_unequip):
                if cur:
                    self.unequip(cur, actor=actor, add_message=add_message)
            # occupy required slots
            for s in req:
                self.slots[s] = item
            # apply tags if actor provided
            if actor and getattr(item, "tags", None):
                for t in item.tags:
                    actor.add_tag(t)
            if add_message:
                self.equip_message(item.name)
            return True

        # Single-slot items with allowed alternatives: prefer main_hand then off_hand
        allowed = getattr(eq, "allowed_slot_options", lambda: [])()
        preferred_order = [MAIN_HAND, OFF_HAND]
        for preferred in preferred_order:
            if preferred in allowed and self.is_slot_free(preferred):
                self.slots[preferred] = item
                if actor and getattr(item, "tags", None):
                    for t in item.tags:
                        actor.add_tag(t)
                if add_message:
                    self.equip_message(item.name)
                return True

        # If no preferred free slot, try any allowed slot (auto-unequip occupant)
        for s in allowed:
            if s in self.slots:
                cur = self.slots[s]
                if cur and cur is not item:
                    self.unequip(cur, actor=actor, add_message=add_message)
                self.slots[s] = item
                if actor and getattr(item, "tags", None):
                    for t in item.tags:
                        actor.add_tag(t)
                if add_message:
                    self.equip_message(item.name)
                return True

        return False

    def unequip(self, item: "Item", actor: Optional["Actor"] = None, add_message: bool = True) -> bool:
        """
        Unequip the given item from any slots it occupies. Returns True if anything changed.
        Removes item tags from actor only when the item is no longer equipped anywhere.
        """
        removed = False
        for s, cur in list(self.slots.items()):
            if cur is item:
                self.slots[s] = None
                removed = True

        if removed:
            # Only remove tags if the item is no longer equipped anywhere
            still_equipped = self.item_is_equipped(item)
            if actor and getattr(item, "tags", None) and not still_equipped:
                for t in item.tags:
                    actor.remove_tag(t)
            if add_message:
                self.unequip_message(item.name)
        return removed

    def toggle_equip(self, item: "Item", actor: Optional["Actor"] = None, add_message: bool = True) -> bool:
        """
        If item is equipped anywhere, unequip it. Otherwise attempt to equip it.
        """
        if self.item_is_equipped(item):
            return self.unequip(item, actor=actor, add_message=add_message)
        return self.equip(item, actor=actor, add_message=add_message)

    # --- Messages (UI) -------------------------------------------------------

    def unequip_message(self, item_name: str) -> None:
        try:
            self.parent.gamemap.engine.message_log.add_message(f"You remove the {item_name}.")
        except Exception:
            # Be tolerant in non-player contexts
            pass

    def equip_message(self, item_name: str) -> None:
        try:
            self.parent.gamemap.engine.message_log.add_message(f"You equip the {item_name}.")
        except Exception:
            pass
