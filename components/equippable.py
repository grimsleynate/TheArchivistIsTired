from __future__ import annotations

from typing import TYPE_CHECKING

from components.base_component import BaseComponent
from equipment_types import EquipmentType

if TYPE_CHECKING:
    from entity import Item

from equipment_slots import normalize_slot_entry

class Equippable:
    def __init__(self,
                 slot: str | None = None,
                 slots: list | None = None,
                 required_slots: list | None = None,
                 allowed_slots: list | None = None,
                 power_bonus: int = 0,
                 defense_bonus: int = 0,
                 two_handed: bool = False,
                 **kwargs):
        # Backwards compatibility: single "slot" -> allowed_slots
        if allowed_slots is None:
            if slots is not None:
                allowed_slots = slots
            elif slot is not None:
                allowed_slots = [slot]

        # Normalize to canonical lists
        self.allowed_slots = normalize_slot_entry(allowed_slots)
        self.required_slots = normalize_slot_entry(required_slots)

        # If two_handed and no explicit required_slots, require both hands
        if two_handed and not self.required_slots:
            self.required_slots = normalize_slot_entry(["twohand"])

        # If required_slots present, they take precedence (item occupies all)
        # If not, allowed_slots defines where it may be placed (one of)
        self.power_bonus = int(power_bonus)
        self.defense_bonus = int(defense_bonus)
        self.two_handed = bool(two_handed)
        self.parent = None

    def occupies_slots(self) -> list[str]:
        """Return the list of slots this item will occupy when equipped.
        For items with required_slots, return that list.
        For items with only allowed_slots, the equipment system will pick one allowed slot."""
        return list(self.required_slots) if self.required_slots else []

    def allowed_slot_options(self) -> list[str]:
        """Return allowed slots (alternatives) for single‑slot items."""
        return list(self.allowed_slots)




class Dagger(Equippable):
    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.WEAPON, power_bonus=2)


class Sword(Equippable):
    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.WEAPON, power_bonus=4)


class LeatherArmor(Equippable):
    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.ARMOR, defense_bonus=1)


class ChainMail(Equippable):
    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.ARMOR, defense_bonus=3)
