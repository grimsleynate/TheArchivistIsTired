from __future__ import annotations

from typing import List, TYPE_CHECKING, Optional

from components.base_component import BaseComponent

if TYPE_CHECKING:
    from entity import Actor, Item


class Inventory(BaseComponent):
    parent: Actor

    def __init__(self, capacity: int):
        self.capacity = capacity
        # Each slot is a stack: List[Item]
        self.slots: List[List[Item]] = []

    def drop(self, item: Item) -> None:
        # Remove from inventory stack
        for stack in self.slots:
            if item in stack:
                stack.remove(item)
                if not stack:
                    self.slots.remove(stack)
                break

        # Clear old parent
        item.parent = None

        # Place item on ground
        item.place(self.parent.x, self.parent.y, self.gamemap)

        # Add to tile stacks
        if self.gamemap:
            self.gamemap.add_item(item, self.parent.x, self.parent.y)

        self.engine.message_log.add_message(f"You dropped the {item.name}.")

    def find_stack(self, item: Item) -> Optional[List[Item]]:
        for stack in self.slots:
            rep = stack[0]

            # Never merge equipped items with unequipped ones
            if self.parent.equipment.item_is_equipped(rep) != self.parent.equipment.item_is_equipped(item):
                continue

            if rep.name == item.name and rep.max_stack == item.max_stack:
                return stack

        return None
    

    def add_item(self, item: Item) -> bool:
        # Try stacking first
        stack = self.find_stack(item)
        if stack and len(stack) < stack[0].max_stack:
            stack.append(item)
            item.parent = self
            return True

        # Otherwise create a new stack if capacity allows (capacity = number of stacks)
        if len(self.slots) < self.capacity:
            self.slots.append([item])
            item.parent = self
            return True

        return False  # inventory full
    
    def remove_from_stack(self, item: Item) -> None:
        """Remove an item from whatever stack it is in."""
        for stack in self.slots:
            if item in stack:
                stack.remove(item)
                if not stack:
                    self.slots.remove(stack)
                return

    def ensure_single_item_stack(self, item: Item) -> None:
        """Ensure this item is in its own stack of length 1."""
        # First remove it from any existing stack
        self.remove_from_stack(item)

        # Then create a new single-item stack
        new_stack = [item]
        item.parent = self
        
        #Insert at top of inventory
        self.slots.insert(0, new_stack)
        
    def merge_unequipped_item(self, item: Item) -> None:
        """After unequipping, merge this item back into an appropriate stack if possible."""
        # Remove its current stack (it should be a single-item stack)
        self.remove_from_stack(item)

        # Now add it back using normal stacking rules
        self.add_item(item)
