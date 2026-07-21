from __future__ import annotations

from inspect import stack
import os

from typing import Callable, Dict, Optional, Tuple, TYPE_CHECKING, Union

import tcod

import actions
from actions import (
    Action,
    BumpAction,
    PickupAction,
    WaitAction,
)
import color
import exceptions

if TYPE_CHECKING:
    from engine import Engine
    from entity import Item


MOVE_KEYS = {
    # Arrow keys.
    tcod.event.K_UP: (0, -1),
    tcod.event.K_DOWN: (0, 1),
    tcod.event.K_LEFT: (-1, 0),
    tcod.event.K_RIGHT: (1, 0),
    tcod.event.K_HOME: (-1, -1),
    tcod.event.K_END: (-1, 1),
    tcod.event.K_PAGEUP: (1, -1),
    tcod.event.K_PAGEDOWN: (1, 1),
    # Numpad keys.
    tcod.event.K_KP_1: (-1, 1),
    tcod.event.K_KP_2: (0, 1),
    tcod.event.K_KP_3: (1, 1),
    tcod.event.K_KP_4: (-1, 0),
    tcod.event.K_KP_6: (1, 0),
    tcod.event.K_KP_7: (-1, -1),
    tcod.event.K_KP_8: (0, -1),
    tcod.event.K_KP_9: (1, -1),
    # Vi keys.
    tcod.event.K_h: (-1, 0),
    tcod.event.K_j: (0, 1),
    tcod.event.K_k: (0, -1),
    tcod.event.K_l: (1, 0),
    tcod.event.K_y: (-1, -1),
    tcod.event.K_u: (1, -1),
    tcod.event.K_b: (-1, 1),
    tcod.event.K_n: (1, 1),
}

WAIT_KEYS = {
    tcod.event.K_PERIOD,
    tcod.event.K_KP_5,
    tcod.event.K_CLEAR,
}

CONFIRM_KEYS = {
    tcod.event.K_RETURN,
    tcod.event.K_KP_ENTER,
}

ActionOrHandler = Union[Action, "BaseEventHandler"]
"""An event handler return value which can trigger an action or switch active handlers.

If a handler is returned then it will become the active handler for future events.
If an action is returned it will be attempted and if it's valid then
MainGameEventHandler will become the active handler.
"""


class BaseEventHandler(tcod.event.EventDispatch[ActionOrHandler]):
    def handle_events(self, event: tcod.event.Event) -> BaseEventHandler:
        """Handle an event and return the next active event handler."""
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        assert not isinstance(state, Action), f"{self!r} can not handle actions."
        return self

    def on_render(self, console: tcod.Console) -> None:
        raise NotImplementedError()

    def ev_quit(self, event: tcod.event.Quit) -> Optional[Action]:
        raise SystemExit()


class PopupMessage(BaseEventHandler):
    """Display a popup text window."""

    def __init__(self, parent_handler: BaseEventHandler, text: str):
        self.parent = parent_handler
        self.text = text

    def on_render(self, console: tcod.Console) -> None:
        """Render the parent and dim the result, then print the message on top."""
        self.parent.on_render(console)
        console.tiles_rgb["fg"] //= 8
        console.tiles_rgb["bg"] //= 8

        console.print(
            console.width // 2,
            console.height // 2,
            self.text,
            fg=color.white,
            bg=color.black,
            alignment=tcod.CENTER,
        )

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[BaseEventHandler]:
        """Any key returns to the parent handler."""
        return self.parent


class EventHandler(BaseEventHandler):
    def __init__(self, engine: Engine):
        self.engine = engine

    def handle_events(self, event: tcod.event.Event) -> BaseEventHandler:
        """Handle events for input handlers with an engine."""
        action_or_state = self.dispatch(event)
        if isinstance(action_or_state, BaseEventHandler):
            return action_or_state
        if self.handle_action(action_or_state):
            # A valid action was performed.
            if not self.engine.player.is_alive:
                # The player was killed sometime during or after the action.
                return GameOverEventHandler(self.engine)
            elif self.engine.player.level.requires_level_up:
                return LevelUpEventHandler(self.engine)
            return MainGameEventHandler(self.engine)  # Return to the main handler.
        return self

    def handle_action(self, action: Optional[Action]) -> bool:
        """Handle actions returned from event methods.

        Returns True if the action will advance a turn.
        """
        if action is None:
            return False

        try:
            action.perform()
        except exceptions.Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], color.impossible)
            return False  # Skip enemy turn on exceptions.

        # After performing the action, if the current handler has a parent, restore it.
        # This closes modal handlers like the context menu and returns to inventory/loot.
        current_handler = getattr(self, "event_handler", None)
        if current_handler is not None and hasattr(current_handler, "parent") and current_handler.parent is not None:
            # Switch back to the parent handler (inventory/loot)
            # Note: if your code stores the active handler somewhere else, use that attribute.
            self.event_handler = current_handler.parent

        # Continue with normal turn advancement
        self.engine.handle_enemy_turns()
        self.engine.update_fov()
        return True


    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> None:
        if self.engine.game_map.in_bounds(event.tile.x, event.tile.y):
            self.engine.mouse_location = event.tile.x, event.tile.y

    def on_render(self, console: tcod.Console) -> None:
        self.engine.render(console)


class AskUserEventHandler(EventHandler):
    """Handles user input for actions which require special input."""

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """By default any key exits this input handler."""
        if event.sym in {  # Ignore modifier keys.
            tcod.event.K_LSHIFT,
            tcod.event.K_RSHIFT,
            tcod.event.K_LCTRL,
            tcod.event.K_RCTRL,
            tcod.event.K_LALT,
            tcod.event.K_RALT,
        }:
            return None
        return self.on_exit()

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> None:
        if not hasattr(self, "row_bounds"):
            return

        mx, my = event.tile.x, event.tile.y

        for i, (x1, y1, x2, y2) in enumerate(self.row_bounds):
            if x1 <= mx < x2 and y1 == my:
                if hasattr(self, "on_mouse_hover"):
                    self.on_mouse_hover(i)
                return

        if hasattr(self, "on_mouse_hover"):
            self.on_mouse_hover(None)

    def ev_mousebuttondown(self, event: tcod.event.MouseButtonDown):
        if not hasattr(self, "row_bounds"):
            return None

        mx, my = event.tile.x, event.tile.y

        for i, (x1, y1, x2, y2) in enumerate(self.row_bounds):
            if x1 <= mx < x2 and y1 == my:
                if hasattr(self, "on_mouse_click"):
                    return self.on_mouse_click(i)
                return None

        return None

    def on_exit(self) -> Optional[ActionOrHandler]:
        """Called when the user is trying to exit or cancel an action.

        By default this returns to the main event handler.
        """
        return MainGameEventHandler(self.engine)


class CharacterScreenEventHandler(AskUserEventHandler):
    TITLE = "Character Information"
    MARGIN = 4

    STAT_ORDER = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    STAT_FULLNAME = {
        "STR": "Strength",
        "DEX": "Dexterity",
        "CON": "Constitution",
        "INT": "Intelligence",
        "WIS": "Wisdom",
        "CHA": "Charisma",
    }

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        # Full-screen minus margin
        x = self.MARGIN
        y = self.MARGIN
        width = console.width - (self.MARGIN * 2)
        height = console.height - (self.MARGIN * 2)

        # Draw frame
        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=height,
            title=self.TITLE,
            clear=True,
            fg=color.menu_title,
            bg=color.black,
        )

        inner_x = x + 2
        inner_y = y + 2
        line = inner_y

        player = self.engine.player

        # --- Header: Name, Race, Subrace ------------------------------------
        name = getattr(player, "name", "Unknown")
        race_name = self._resolve_name(getattr(player, "race", None), getattr(player, "race_id", None))
        subrace_name = self._resolve_name(getattr(player, "subrace", None), getattr(player, "subrace_id", None))

        console.print(inner_x, line, f"{name}", fg=color.menu_text)
        line += 1
        console.print(inner_x, line, f"Race: {race_name}", fg=color.menu_text)
        line += 1
        if subrace_name:
            console.print(inner_x, line, f"Subrace: {subrace_name}", fg=color.menu_text)
            line += 1

        # --- Level / XP / Combat stats --------------------------------------
        # Keep these near the top-left
        lvl = getattr(player, "level", None)
        if lvl:
            try:
                lvl_str = f"Level: {lvl.current_level}  XP: {lvl.current_xp}  Next: {lvl.experience_to_next_level}"
            except Exception:
                lvl_str = f"Level: {getattr(lvl, 'current_level', '?')}"
            console.print(inner_x, line, lvl_str, fg=color.menu_text)
            line += 1

        # Attack / Defense
        try:
            atk = player.fighter.power
            df = player.fighter.defense
            console.print(inner_x, line, f"Attack: {atk}   Defense: {df}", fg=color.menu_text)
            line += 2
        except Exception:
            line += 1

        # --- Stats table header ----------------------------------------------
        stats_x = inner_x
        stats_y = line
        col_widths = (18, 8, 8, 8, 8)  # label, base, mod, total, prof
        # Header row
        console.print(stats_x, stats_y, "Attribute".ljust(col_widths[0]), fg=color.menu_title)
        console.print(stats_x + col_widths[0], stats_y, "Base".rjust(col_widths[1]), fg=color.menu_title)
        console.print(stats_x + col_widths[0] + col_widths[1], stats_y, "Mod".rjust(col_widths[2]), fg=color.menu_title)
        console.print(stats_x + col_widths[0] + col_widths[1] + col_widths[2], stats_y, "Total".rjust(col_widths[3]), fg=color.menu_title)
        console.print(stats_x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3], stats_y, "Prof".rjust(col_widths[4]), fg=color.menu_title)
        stats_y += 1

        # --- Gather attribute data -------------------------------------------
        # Base attributes: try player.base_attributes or player.get_base_attribute
        base_attrs = getattr(player, "base_attributes", None) or {}
        get_base_attr = getattr(player, "get_base_attribute", None)

        # Race/subrace/class modifiers: try to read from objects if present
        race_mods = self._collect_attr_mods_from_source(getattr(player, "race", None))
        subrace_mods = self._collect_attr_mods_from_source(getattr(player, "subrace", None))
        class_mods = self._collect_attr_mods_from_source(getattr(player, "class_obj", None))  # optional

        # Equipment and active effects modifiers
        equip_mods = self._collect_attr_mods_from_equipment(getattr(player, "equipment", None))
        active_mods = getattr(player, "active_attribute_modifiers", {}) or {}

        # For each stat, compute base, modifiers, total, proficiency
        for stat in self.STAT_ORDER:
            # Base value: prefer explicit getter, else base_attrs, else 8 default
            if callable(get_base_attr):
                try:
                    base_val = int(get_base_attr(stat))
                except Exception:
                    base_val = int(base_attrs.get(stat, 8))
            else:
                base_val = int(base_attrs.get(stat, 8))

            # Add race/subrace/class additive modifiers (these are considered part of "base" for display)
            race_add = int(race_mods.get(stat, 0))
            subrace_add = int(subrace_mods.get(stat, 0))
            class_add = int(class_mods.get(stat, 0))
            composed_base = base_val + race_add + subrace_add + class_add

            # Current modifiers (equipment + active effects)
            equip_add = int(equip_mods.get(stat, 0))
            active_add = int(active_mods.get(stat, 0))
            current_modifiers = equip_add + active_add

            total_current = composed_base + current_modifiers

            # Proficiency: try actor method or dict, else fallback compute
            prof = self._resolve_proficiency(player, stat, total_current)

            # Colors: negative modifiers in red, prof <=0 in gray
            mod_color = color.menu_text
            if current_modifiers < 0:
                mod_color = color.red
            prof_color = color.menu_text
            if prof <= 0:
                prof_color = color.gray

            # Render row
            label = f"{self.STAT_FULLNAME.get(stat, stat)} ({stat})"
            console.print(stats_x, stats_y, label.ljust(col_widths[0]), fg=color.menu_text)
            console.print(stats_x + col_widths[0], stats_y, f"{composed_base}".rjust(col_widths[1]), fg=color.menu_text)
            # show modifier with sign
            mod_str = f"{current_modifiers:+d}"
            console.print(stats_x + col_widths[0] + col_widths[1], stats_y, mod_str.rjust(col_widths[2]), fg=mod_color)
            console.print(stats_x + col_widths[0] + col_widths[1] + col_widths[2], stats_y, f"{total_current}".rjust(col_widths[3]), fg=color.menu_text)
            console.print(stats_x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3], stats_y, f"{prof}".rjust(col_widths[4]), fg=prof_color)
            stats_y += 1

        # --- Tags and descriptions -------------------------------------------
        tags_x = stats_x
        tags_y = stats_y + 1
        console.print(tags_x, tags_y, "Tags:", fg=color.menu_title)
        tags_y += 1

        # Use the engine's tag repository (loaded from data/tags.json)
        tag_defs = getattr(self.engine, "tag_defs", {}) or {}
        player_tags = getattr(player, "tags", []) or []

        if not player_tags:
            console.print(tags_x, tags_y, "(none)", fg=color.menu_text)
            tags_y += 1
        else:
            for t in player_tags:
                info = tag_defs.get(t)
                name = info["name"] if info else t
                desc = info["description"] if info else "(no description)"
                console.print(tags_x, tags_y, f"{name}: {desc}", fg=color.menu_text)
                tags_y += 1


        # Done

    # ----------------- Helper methods ---------------------------------------

    def _resolve_name(self, obj: Optional[object], fallback_id: Optional[str]) -> str:
        """
        Resolve a human name for race/subrace/class objects or fallback id strings.
        Accepts dicts or objects with .name or .get('name').
        """
        if obj is None:
            return fallback_id or ""
        if isinstance(obj, dict):
            return obj.get("name", fallback_id or "")
        return getattr(obj, "name", fallback_id or "")

    def _collect_attr_mods_from_source(self, src: Optional[object]) -> Dict[str, int]:
        """
        Read attribute modifiers from a source object (race, subrace, class).
        Accepts dicts with 'attributes' or objects with .attributes.
        Returns a dict mapping stat -> additive int.
        """
        if not src:
            return {}
        if isinstance(src, dict):
            return {k: int(v) for k, v in (src.get("attributes", {}) or {}).items()}
        return getattr(src, "attributes", {}) or {}

    def _collect_attr_mods_from_equipment(self, equipment) -> Dict[str, int]:
        """
        Sum attribute modifiers provided by equipped items.
        Looks for equippable component with properties like 'power_bonus' etc.
        Also checks item.properties for stat modifiers under 'modifiers' key.
        """
        out: Dict[str, int] = {}
        if not equipment:
            return out

        # equipment.slots is expected to be a mapping slot -> Item
        slots = getattr(equipment, "slots", None) or {}
        for item in set(slots.values()):
            if not item:
                continue
            # 1) equippable component numeric bonuses (power/defense) are not per-stat;
            #    but items may include properties.modifiers = {"DEX": -1, ...}
            props = getattr(item, "properties", {}) or {}
            mods = props.get("modifiers", {}) or {}
            for k, v in mods.items():
                try:
                    out[k] = out.get(k, 0) + int(v)
                except Exception:
                    pass

            # 2) Some items may expose equippable.stat_mods or similar
            eq = getattr(item, "equippable", None)
            if eq:
                stat_mods = getattr(eq, "stat_mods", None) or getattr(eq, "modifiers", None) or {}
                if isinstance(stat_mods, dict):
                    for k, v in stat_mods.items():
                        try:
                            out[k] = out.get(k, 0) + int(v)
                        except Exception:
                            pass

        return out

    def _resolve_proficiency(self, player, stat: str, total_current: int) -> int:
        """
        Resolve proficiency for a stat. Prefer existing actor methods/fields:
          - player.get_proficiency(stat)
          - player.proficiencies dict
        Fallback: compute a simple derived proficiency so UI shows something useful.
        The fallback formula is intentionally conservative and yields non-negative values.
        """
        # 1) method
        get_prof = getattr(player, "get_proficiency", None)
        if callable(get_prof):
            try:
                return int(get_prof(stat))
            except Exception:
                pass

        # 2) dict
        profs = getattr(player, "proficiencies", None) or {}
        if isinstance(profs, dict) and stat in profs:
            try:
                return int(profs[stat])
            except Exception:
                pass

        # 3) fallback compute: map total_current into a small proficiency number
        #    This is a conservative fallback: higher total -> higher proficiency.
        #    Formula: floor((total_current - 8) / 4), min 0
        try:
            p = (int(total_current) - 8) // 4
            return max(0, int(p))
        except Exception:
            return 0


class LevelUpEventHandler(AskUserEventHandler):
    TITLE = "Level Up"

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        console.draw_frame(
            x=x,
            y=0,
            width=35,
            height=8,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        console.print(x=x + 1, y=1, string="Congratulations! You level up!")
        console.print(x=x + 1, y=2, string="Select an attribute to increase.")

        console.print(
            x=x + 1,
            y=4,
            string=f"a) Constitution (+20 HP, from {self.engine.player.fighter.max_hp})",
        )
        console.print(
            x=x + 1,
            y=5,
            string=f"b) Strength (+1 attack, from {self.engine.player.fighter.power})",
        )
        console.print(
            x=x + 1,
            y=6,
            string=f"c) Agility (+1 defense, from {self.engine.player.fighter.defense})",
        )

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.K_a

        if 0 <= index <= 2:
            if index == 0:
                player.level.increase_max_hp()
            elif index == 1:
                player.level.increase_power()
            else:
                player.level.increase_defense()
        else:
            self.engine.message_log.add_message("Invalid entry.", color.invalid)

            return None

        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """
        Don't allow the player to click to exit the menu, like normal.
        """
        return None


class PickupMenuHandler(AskUserEventHandler):
    TITLE = "Pick up items"

    def __init__(self, engine: Engine):
        super().__init__(engine)
        px, py = engine.player.x, engine.player.y
        self.x = px
        self.y = py
        # Stacks of items on this tile
        self.stacks = engine.game_map.get_items_at(px, py)
        
        if not self.stacks:
            raise exceptions.Impossible("There are no items here to pick up.")

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        height = len(self.stacks) + 3
        if height < 3:
            height = 3

        x = 40 if self.engine.player.x <= 30 else 0
        y = 0
        width = int((len(self.TITLE) + 4) * 2.0)

        console.draw_frame(
            x=x, y=y, width=width, height=height,
            title=self.TITLE, clear=True,
            fg=(255, 255, 255), bg=(0, 0, 0),
        )

        self.row_bounds = []

        for i, stack in enumerate(self.stacks):
            row_y = y + 1 + i
            row_x1 = x + 1
            row_x2 = x + width - 1
            self.row_bounds.append((row_x1, row_y, row_x2, row_y))

        for i, stack in enumerate(self.stacks):
            item = stack[0]
            count = len(stack)
            key = chr(ord("a") + i)

            if count > 1:
                console.print(x + 1, y + i + 1, f"({key}) {item.name} ({count})")
            else:
                console.print(x + 1, y + i + 1, f"({key}) {item.name}")

        console.print(x + 1, y + height - 2, "(Tab) Pick up all")

    def ev_keydown(self, event: tcod.event.KeyDown):
        key = event.sym
        player = self.engine.player
        inventory = player.inventory

        # --- TAB: pick up everything (unchanged) ---
        if key == tcod.event.K_TAB:
            for stack in list(self.stacks):
                while stack:
                    item = stack.pop()

                    if len(inventory.slots) >= inventory.capacity:
                        self.engine.message_log.add_message("Your inventory is full.", color.invalid)
                        stack.append(item)
                        break

                    self.engine.game_map.remove_item(item, self.x, self.y)
                    if item in self.engine.game_map.entities:
                        self.engine.game_map.entities.remove(item)

                    item.parent = inventory
                    inventory.add_item(item)

                    self.engine.message_log.add_message(f"You picked up the {item.name}!")

                if not stack:
                    self.stacks.remove(stack)

            return super().ev_keydown(event)

        # --- LETTER KEYS: open tile context menu instead of picking up ---
        if tcod.event.K_a <= key <= tcod.event.K_z:
            index = key - tcod.event.K_a

            if index >= len(self.stacks):
                self.engine.message_log.add_message("Invalid entry.", color.invalid)
                return None

            stack = self.stacks[index]
            if not stack:
                self.engine.message_log.add_message("Nothing to pick up.", color.invalid)
                return None

            # The item we will show the context menu for
            item = stack[-1]   # DO NOT pop here — context menu decides what to do

            # Compute anchor position (same as inventory)
            row_x, row_y, row_width = self.get_row_anchor(index)

            # Open tile context menu
            return PickupContextMenuHandler(
                self.engine,
                item,
                anchor_x=row_x,
                anchor_y=row_y,
                anchor_width=row_width,
                parent=self,
            )

        # --- ENTER: pick up highlighted item (unchanged) ---
        if key == tcod.event.K_RETURN:
            return self.pickup_highlighted_item()

        # --- Arrow keys (unchanged) ---
        if key == tcod.event.K_UP:
            return self.move_highlight(-1)
        if key == tcod.event.K_DOWN:
            return self.move_highlight(1)

        return super().ev_keydown(event)

    def on_mouse_hover(self, index):
        self.highlight_index = index

    def on_mouse_click(self, index):
        stack = self.stacks[index]
        if stack:
            item = stack.pop()

    def get_row_anchor(self, index):
        """
        Returns (x, y, width) for the row at the given index,
        matching the inventory menu’s anchor logic.
        """

        # The pickup menu prints items starting at some base Y.
        # You already know where your pickup menu draws rows.
        # This matches the inventory menu’s pattern:
        base_x = self.x  # or whatever your pickup menu uses
        base_y = self.y  # same as above

        # PickupMenuHandler draws each stack on its own line.
        row_y = base_y + index
        row_x = base_x

        # Compute width from the longest item name in the stack
        stack = self.stacks[index]
        longest = max((len(item.name) for item in stack), default=1)
        row_width = longest

        return row_x, row_y, row_width

    def pickup_specific_item(self, item):
        player = self.engine.player
        inventory = player.inventory

        # Find the stack containing this item
        for stack in list(self.stacks):
            if item in stack:
                # same logic you use in ev_keydown for single pickup
                if len(inventory.slots) >= inventory.capacity:
                    self.engine.message_log.add_message("Your inventory is full.", color.invalid)
                    return None

                stack.remove(item)
                if not stack:
                    self.stacks.remove(stack)

                self.engine.game_map.remove_item(item, self.x, self.y)
                if item in self.engine.game_map.entities:
                    self.engine.game_map.entities.remove(item)

                item.parent = inventory
                inventory.add_item(item)

                self.engine.message_log.add_message(f"You picked up the {item.name}!")
                return None

        raise exceptions.Impossible("That item is not here.")

    def should_close(self):
        # No stacks left → close
        if not self.stacks:
            return True

        # If the only option left is "(Tab) Pick up all", meaning no lettered items
        # then close the menu.
        # Letter keys correspond to stacks; if stacks exist but all are empty, close.
        for stack in self.stacks:
            if stack:  # at least one item still present
                return False

        return True


class InventoryEventHandler(AskUserEventHandler):  
    """This handler lets the user select an item.

    What happens then depends on the subclass.
    """

    TITLE = "<missing title>"
    
    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.highlight_index: Optional[int] = None

    def get_row_anchor(self, index: int) -> tuple[int, int, int]:
        """
        Return (row_x, row_y, row_width). If modal geometry isn't available yet,
        return a centered fallback so the context menu still opens.
        """
        # If we have modal geometry, compute exact anchor
        if hasattr(self, "console") and hasattr(self, "_modal_x"):
            modal_x = self._modal_x
            modal_y = self._modal_y
            modal_width = self._modal_width

            row_x = modal_x + 2                 # match your render offsets
            row_y = modal_y + 2 + index         # match your render offsets
            row_width = modal_width - 4
            return row_x, row_y, row_width

        # Fallback: center the menu on screen
        screen_w = getattr(self, "console", None).width if hasattr(self, "console") else 80
        screen_h = getattr(self, "console", None).height if hasattr(self, "console") else 25
        fallback_w = min(30, screen_w - 4)
        fallback_h = 6
        center_x = max(0, (screen_w - fallback_w) // 2)
        center_y = max(0, (screen_h - fallback_h) // 2)
        return center_x, center_y, fallback_w


    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        
        self.console = console

        inventory = self.engine.player.inventory
        number_of_stacks = len(inventory.slots)

        inv_width = int(console.width * 0.85)
        inv_height = int(console.height * 0.85)

        x = (console.width - inv_width) // 2
        y = (console.height - inv_height) // 2
        
        self._modal_x = x
        self._modal_y = y
        self._modal_width = inv_width
        self._modal_height = inv_height

        console.draw_frame(
            x=x,
            y=y,
            width=inv_width,
            height=inv_height,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        self.row_bounds = []
        
        for i, stack in enumerate(inventory.slots):
            row_y = y + 2 + i
            row_x1 = x + 2
            row_x2 = x + inv_width - 2
            self.row_bounds.append((row_x1, row_y, row_x2, row_y))

        if number_of_stacks > 0:
            for i, stack in enumerate(inventory.slots):
                item_key = chr(ord("a") + i)
                item = stack[0]
                count = len(stack)

                is_equipped = self.engine.player.equipment.item_is_equipped(item)

                if count > 1:
                    item_string = f"({item_key}) {item.name} ({count})"
                else:
                    item_string = f"({item_key}) {item.name}"

                if is_equipped:
                    item_string += " (E)"

                fg = (255, 255, 255)
                bg = (50, 50, 150) if self.highlight_index == i else (0, 0, 0)

                console.print(x + 2, y + 2 + i, item_string, fg=fg, bg=bg)
        else:
            console.print(x + 2, y + 2, "(Empty)")

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym

        if key == tcod.event.K_DOWN:
            return self.move_highlight(1)

        if key == tcod.event.K_UP:
            return self.move_highlight(-1)

        if key == tcod.event.K_RETURN:
            return self.activate_highlighted_item()
        
        if key == tcod.event.K_ESCAPE:
            return self.on_exit()

        index = key - tcod.event.K_a
        if 0 <= index <= 26:
            try:
                stack = self.engine.player.inventory.slots[index]
                selected_item = stack[0]
            except IndexError:
                self.engine.message_log.add_message("Invalid entry.", color.invalid)
                return None
            return self.on_item_selected(selected_item)

        return None
    
        if self.highlight_index is None:
            return None

        slots = self.engine.player.inventory.slots
        if not slots:
            return None

        item = slots[self.highlight_index][0]
        return self.on_item_selected(item)
    
    def on_exit(self):
        # Return to main game handler
        return MainGameEventHandler(self.engine)

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Called when the user selects a valid item."""
        raise NotImplementedError()
    
    def move_highlight(self, direction: int) -> None:
        slots = self.engine.player.inventory.slots
        if not slots:
            return None

        if self.highlight_index is None:
            self.highlight_index = 0
        else:
            self.highlight_index = (self.highlight_index + direction) % len(slots)

        return None

    def activate_highlighted_item(self) -> Optional[ActionOrHandler]:
        if self.highlight_index is None:
            return None

        slots = self.engine.player.inventory.slots
        if not slots:
            return None

        item = slots[self.highlight_index][0]
        return self.on_item_selected(item)

    def on_mouse_hover(self, index):
        self.highlight_index = index

    def on_mouse_click(self, index):
        item = self.engine.player.inventory.slots[index][0]
        return self.on_item_selected(item)


class InventoryActivateHandler(InventoryEventHandler):
    """Handle using an inventory item."""

    TITLE = "Select an item to use"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        try:
            index = next(i for i, stack in enumerate(self.engine.player.inventory.slots) if stack and stack[0] is item)
        except StopIteration:
            # fallback: open centered if we can't find the row
            return ContextMenuHandler(self.engine, item, anchor_x=0, anchor_y=0, anchor_width=10, parent=self)

        # compute anchor using stored modal geometry
        row_x, row_y, row_width = self.get_row_anchor(index)

        return ContextMenuHandler(self.engine, item, anchor_x=row_x, anchor_y=row_y, anchor_width=row_width, parent=self)
        
        
class ContextMenuHandler(AskUserEventHandler):
    """Context menu anchored to an item row.

    anchor_x, anchor_y are console coordinates of the row that opened the menu.
    anchor_width is the width of that row (so we can place the menu to the right).
    """

    PADDING_X = 2
    PADDING_Y = 1

    def __init__(self, engine, item: Item, anchor_x: int, anchor_y: int, anchor_width: int, parent: Optional[EventHandler] = None):
        super().__init__(engine)
        self.item = item
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y
        self.anchor_width = anchor_width
        self.parent = parent

        # highlight index for keyboard/mouse
        self.highlight_index = None

        # computed each render
        self.row_bounds = []
        self.console = None

    def get_options(self):
        options = []
        if self.item.consumable:
            options.append(("(u)se", self.use_item))
        if self.item.equippable:
            options.append(("(e)quip/unequip", self.toggle_equip))
        options.append(("(d)rop", self.drop_item))
        options.append(("(l)ook", self.inspect_item))
        options.append(("Cancel", self.close_menu))
        return options

    def on_render(self, console: tcod.Console):
        # Render the parent first so the context menu is layered on top
        if self.parent is not None:
            try:
                # Parent should implement on_render(console)
                self.parent.on_render(console)
            except Exception:
                # If parent rendering fails, fall back to engine-level render
                super().on_render(console)

        # store console for mouse handlers
        self.console = console

        self._options = options = self.get_options()
        if not options:
            return

        # compute width from longest label and item name
        labels = [label for label, _ in options]
        longest_label = max(labels, key=len)
        content_width = max(len(longest_label), len(self.item.name))

        menu_width = content_width + self.PADDING_X * 2
        menu_height = len(options) + self.PADDING_Y * 2 + 1  # +1 for title row

        # try to place to the right of the anchor
        preferred_x = self.anchor_x + self.anchor_width + 1
        screen_w = console.width
        screen_h = console.height

        if preferred_x + menu_width <= screen_w:
            x = preferred_x
        else:
            left_x = self.anchor_x - menu_width - 1
            if left_x >= 0:
                x = left_x
            else:
                x = max(0, screen_w - menu_width)

        # vertical placement: align top with anchor row if possible, clamp to screen
        y = self.anchor_y - (self.PADDING_Y + 1)
        if y < 0:
            y = 0
        if y + menu_height > screen_h:
            y = max(0, screen_h - menu_height)

        # draw frame (this will overlay the parent)
        console.draw_frame(
            x=x, y=y, width=menu_width, height=menu_height,
            title=self.item.name, clear=True,
            fg=(255, 255, 255), bg=(0, 0, 0),
        )

        # draw options and build row bounds
        self.row_bounds = []
        for i, (label, _) in enumerate(options):
            row_y = y + self.PADDING_Y + 1 + i  # +1 to leave a line after title
            row_x = x + self.PADDING_X
            bg = (50, 50, 150) if self.highlight_index == i else (0, 0, 0)
            console.print(row_x, row_y, label.ljust(content_width), fg=(255,255,255), bg=bg)

            # bounds: x1, y1, x2 (exclusive), y2
            self.row_bounds.append((row_x, row_y, row_x + content_width, row_y + 1))

    # keyboard handling
    def ev_keydown(self, event: tcod.event.KeyDown):
        key = event.sym

        # Close
        if key == tcod.event.K_ESCAPE:
            return self.close_menu()

        # Navigation
        if key == tcod.event.K_UP:
            return self.move_highlight(-1)
        if key == tcod.event.K_DOWN:
            return self.move_highlight(1)
        if key == tcod.event.K_RETURN:
            return self.activate_highlighted_item()

        # Ensure we use the same option list that was rendered this frame
        options = getattr(self, "_options", None)
        if options is None:
            options = self.get_options()

        # Helper: find option index by label prefix (case-insensitive)
        def find_option_index(prefix: str) -> int | None:
            lower = prefix.lower()
            for i, (label, _) in enumerate(options):
                if label.lower().startswith(lower):
                    return i
            return None

        # Letter mappings (only these are allowed)
        if key == tcod.event.K_u:  # Use
            idx = find_option_index("(u)se")
            if idx is not None:
                self.highlight_index = idx
                _, action = options[idx]
                return action()
            return None

        if key == tcod.event.K_e:  # Equip / Unequip
            idx = find_option_index("(e)quip/unequip")
            if idx is not None:
                self.highlight_index = idx
                _, action = options[idx]
                return action()
            return None

        if key == tcod.event.K_d:  # Drop
            idx = find_option_index("(d)rop")
            if idx is not None:
                self.highlight_index = idx
                _, action = options[idx]
                return action()
            return None

        if key == tcod.event.K_l:  # Look / Inspect
            idx = find_option_index("(l)ook")
            if idx is not None:
                self.highlight_index = idx
                _, action = options[idx]
                return action()
            return None

        # If we get here, the key is not handled — consume it (do nothing)
        return None

    def _execute_option_and_close(self, index):
        """Execute the option at index, then close the context menu (return parent handler)."""
        options = getattr(self, "_options", None)
        if options is None:
            options = self.get_options()

        if not (0 <= index < len(options)):
            return None

        _, action_callable = options[index]

        # Call the option to get either an Action or an EventHandler or None
        result = action_callable()

        # If the callable returned an EventHandler, switch to it
        if isinstance(result, EventHandler):
            return result

        # If the callable returned an Action-like object, ask the engine to execute it.
        # Many engines expose engine.handle_action(action) or engine.perform_action(action).
        # Try common method names defensively.
        if result is not None:
            if hasattr(self.engine, "handle_action"):
                # typical pattern: engine.handle_action(action) executes it and advances the game
                self.engine.handle_action(result)
            elif hasattr(self.engine, "perform_action"):
                self.engine.perform_action(result)
            else:
                # Fallback: if your engine expects the handler to return the action,
                # return the action so the engine executes it. But we also want to close the menu.
                # In that case, return the action (so it executes) — the engine will keep the current handler,
                # so we also return the parent handler to switch back. If your engine cannot accept
                # a tuple, you must implement handle_action on the engine.
                return result

        # After executing the action, return to the parent handler (inventory/loot)
        return self.parent or InventoryActivateHandler(self.engine)

    def move_highlight(self, direction: int):
        options = self.get_options()
        count = len(options)
        if count == 0:
            return None

        if self.highlight_index is None:
            self.highlight_index = 0
        else:
            self.highlight_index = (self.highlight_index + direction) % count
        return None
    
    def _get_option_result(self, index):
        options = getattr(self, "_options", None)
        if options is None:
            options = self.get_options()
        if not (0 <= index < len(options)):
            return None
        _, action_callable = options[index]
        return action_callable()

    def on_mouse_click(self, index):
        if index is None:
            return self.close_menu()
        return self._get_option_result(index)
    
    def on_mouse_hover(self, index):
        """Called by the mouse dispatcher with the row index or None.

        Sets highlight_index only when the index maps to a rendered option.
        """
        if index is None:
            self.highlight_index = None
            return None

        options = getattr(self, "_options", None) or self.get_options()
        if 0 <= index < len(options):
            self.highlight_index = index
        else:
            self.highlight_index = None
        return None

    # Optional: call this once after the first render to immediately sync highlight
    def sync_hover_from_mouse(self, mx: int = None, my: int = None):
        """Set highlight_index from current mouse tile coordinates.

        If mx/my are omitted, try to read current mouse state via tcod (if available).
        Call this after on_render has built self.row_bounds.
        """
        try:
            if mx is None or my is None:
                state = tcod.event.get_mouse_state()
                mx, my = state.tile.x, state.tile.y
        except Exception:
            # tcod API may differ in your loop; caller can pass mx,my explicitly
            return

        for i, (x1, y1, x2, y2) in enumerate(self.row_bounds):
            if x1 <= mx < x2 and y1 <= my < y2:
                self.highlight_index = i
                return
        self.highlight_index = None


    def activate_highlighted_item(self):
        if self.highlight_index is None:
            return None
        return self._get_option_result(self.highlight_index)

    # actions
    def use_item(self):
        if self.item.consumable:
            return self.item.consumable.get_action(self.engine.player)
        return self.close_menu()

    def toggle_equip(self):
        return actions.EquipAction(self.engine.player, self.item)

    def drop_item(self):
        return actions.DropItem(self.engine.player, self.item)

    def inspect_item(self):
        self.engine.message_log.add_message(self.item.description)
        return None

    def close_menu(self):
        return InventoryActivateHandler(self.engine)


class PickupContextMenuHandler(AskUserEventHandler):
    """Context menu for items on the ground."""

    PADDING_X = 2
    PADDING_Y = 1

    def __init__(self, engine, item, anchor_x, anchor_y, anchor_width, parent=None):
        super().__init__(engine)
        self.item = item
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y
        self.anchor_width = anchor_width
        self.parent = parent

        self.highlight_index = None
        self.row_bounds = []
        self.console = None
        
    def on_render(self, console: tcod.Console):
        # Render the pickup menu underneath
        if self.parent is not None:
            self.parent.on_render(console)

        self.console = console

        # Compute options once
        self._options = options = self.get_options()
        if not options:
            return

        # Compute width
        labels = [label for label, _ in options]
        longest_label = max(labels, key=len)
        content_width = max(len(longest_label), len(self.item.name))

        menu_width = content_width + self.PADDING_X * 2
        menu_height = len(options) + self.PADDING_Y * 2 + 1

        # Positioning (same logic as inventory context menu)
        preferred_x = self.anchor_x + self.anchor_width + 1
        screen_w = console.width
        screen_h = console.height

        if preferred_x + menu_width <= screen_w:
            x = preferred_x
        else:
            left_x = self.anchor_x - menu_width - 1
            if left_x >= 0:
                x = left_x
            else:
                x = max(0, screen_w - menu_width)

        y = self.anchor_y - (self.PADDING_Y + 1)
        if y < 0:
            y = 0
        if y + menu_height > screen_h:
            y = max(0, screen_h - menu_height)

        # Draw frame
        console.draw_frame(
            x=x, y=y, width=menu_width, height=menu_height,
            title=self.item.name, clear=True,
            fg=(255, 255, 255), bg=(0, 0, 0),
        )

        # Draw options + build row bounds
        self.row_bounds = []
        for i, (label, _) in enumerate(options):
            row_y = y + self.PADDING_Y + 1 + i
            row_x = x + self.PADDING_X
            bg = (50, 50, 150) if self.highlight_index == i else (0, 0, 0)
            console.print(row_x, row_y, label.ljust(content_width), fg=(255,255,255), bg=bg)

            self.row_bounds.append((row_x, row_y, row_x + content_width, row_y + 1))
    
    def get_options(self):
        return [
            ("(g)rab", self.grab_item),
            ("(l)ook", self.inspect_item),
            ("cancel", self.close_menu),
        ]

    # --- actions ---
    def grab_item(self):
        # delegate to the pickup menu, then close the context menu
        if isinstance(self.parent, PickupMenuHandler):
            self.parent.pickup_specific_item(self.item)
        return self.close_menu()


    def inspect_item(self):
        self.engine.message_log.add_message(self.item.description)
        return None

    def close_menu(self):
        # If opened from a pickup menu, return to that menu
        if isinstance(self.parent, PickupMenuHandler):
            return self.parent

        # Fallback: inventory screen (only if somehow opened from inventory)
        return InventoryActivateHandler(self.engine)

    # --- mouse + keyboard activation ---
    def ev_keydown(self, event):
        key = event.sym

        if key == tcod.event.K_ESCAPE:
            return self.close_menu()

        if key == tcod.event.K_g:  # Grab
            return self.grab_item()

        if key == tcod.event.K_l:  # Look / Inspect
            return self.inspect_item()

        if key == tcod.event.K_RETURN:
            return self.activate_highlighted_item()

        if key == tcod.event.K_UP:
            return self.move_highlight(-1)

        if key == tcod.event.K_DOWN:
            return self.move_highlight(1)

        return None

    def _get_option_result(self, index):
        options = getattr(self, "_options", None) or self.get_options()
        if 0 <= index < len(options):
            _, action_callable = options[index]
            return action_callable()
        return None

    def on_mouse_click(self, index):
        if index is None:
            return self.close_menu()
        return self._get_option_result(index)

    def activate_highlighted_item(self):
        if self.highlight_index is None:
            return None
        return self._get_option_result(self.highlight_index)

    def on_mouse_hover(self, index):
        options = getattr(self, "_options", None) or self.get_options()
        if index is None or not (0 <= index < len(options)):
            self.highlight_index = None
        else:
            self.highlight_index = index


class InventoryDropHandler(InventoryEventHandler):
    """Handle dropping an inventory item."""

    TITLE = "Select an item to drop"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Drop this item."""
        return actions.DropItem(self.engine.player, item)


class SelectIndexHandler(AskUserEventHandler):
    """Handles asking the user for an index on the map."""

    def __init__(self, engine: Engine):
        """Sets the cursor to the player when this handler is constructed."""
        super().__init__(engine)
        player = self.engine.player
        engine.mouse_location = player.x, player.y

    def on_render(self, console: tcod.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)
        x, y = self.engine.mouse_location
        console.tiles_rgb["bg"][x, y] = color.white
        console.tiles_rgb["fg"][x, y] = color.black

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """Check for key movement or confirmation keys."""
        key = event.sym
        if key in MOVE_KEYS:
            modifier = 1  # Holding modifier keys will speed up key movement.
            if event.mod & (tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT):
                modifier *= 5
            if event.mod & (tcod.event.KMOD_LCTRL | tcod.event.KMOD_RCTRL):
                modifier *= 10
            if event.mod & (tcod.event.KMOD_LALT | tcod.event.KMOD_RALT):
                modifier *= 20

            x, y = self.engine.mouse_location
            dx, dy = MOVE_KEYS[key]
            x += dx * modifier
            y += dy * modifier
            # Clamp the cursor index to the map size.
            x = max(0, min(x, self.engine.game_map.width - 1))
            y = max(0, min(y, self.engine.game_map.height - 1))
            self.engine.mouse_location = x, y
            return None
        elif key in CONFIRM_KEYS:
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """Left click confirms a selection."""
        if self.engine.game_map.in_bounds(*event.tile):
            if event.button == 1:
                return self.on_index_selected(*event.tile)
        return super().ev_mousebuttondown(event)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        """Called when an index is selected."""
        raise NotImplementedError()


class LookHandler(SelectIndexHandler):
    """Lets the player look around using the keyboard."""

    def on_index_selected(self, x: int, y: int) -> MainGameEventHandler:
        """Return to main handler."""
        return MainGameEventHandler(self.engine)


class SingleRangedAttackHandler(SelectIndexHandler):
    """Handles targeting a single enemy. Only the enemy selected will be affected."""

    def __init__(
        self, engine: Engine, callback: Callable[[Tuple[int, int]], Optional[Action]]
    ):
        super().__init__(engine)

        self.callback = callback

    def on_index_selected(self, x: int, y: int) -> Optional[Action]:
        return self.callback((x, y))


class AreaRangedAttackHandler(SelectIndexHandler):
    """Handles targeting an area within a given radius. Any entity within the area will be affected."""

    def __init__(
        self,
        engine: Engine,
        radius: int,
        callback: Callable[[Tuple[int, int]], Optional[Action]],
    ):
        super().__init__(engine)

        self.radius = radius
        self.callback = callback

    def on_render(self, console: tcod.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)

        x, y = self.engine.mouse_location

        # Draw a rectangle around the targeted area, so the player can see the affected tiles.
        console.draw_frame(
            x=x - self.radius - 1,
            y=y - self.radius - 1,
            width=self.radius ** 2,
            height=self.radius ** 2,
            fg=color.red,
            clear=False,
        )

    def on_index_selected(self, x: int, y: int) -> Optional[Action]:
        return self.callback((x, y))


class MainGameEventHandler(EventHandler):
    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        action: Optional[Action] = None

        key = event.sym
        modifier = event.mod

        player = self.engine.player

        if key == tcod.event.K_PERIOD and modifier & (
            tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT
        ):
            return actions.TakeStairsAction(player)

        if key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            action = BumpAction(player, dx, dy)
        elif key in WAIT_KEYS:
            action = WaitAction(player)

        elif key == tcod.event.K_ESCAPE:
            raise SystemExit()
        elif key == tcod.event.K_v:
            return HistoryViewer(self.engine)

        elif key == tcod.event.K_g:
            px, py = self.engine.player.x, self.engine.player.y
            items_here = self.engine.game_map.get_items_at(px, py)

            if not items_here:
                raise exceptions.Impossible("There is nothing here to pick up.")

            if len(items_here) == 1:
                items_here = self.engine.game_map.get_items_at(player.x, player.y)

                if not items_here:
                    raise exceptions.Impossible("There is nothing here to pick up.")

                if len(items_here) > 1:
                    # open pickup menu
                    return PickupMenuHandler(self.engine, player.x, player.y)

                # exactly one stack
                stack = items_here[0]
                item = stack[-1]   # DO NOT pop here

                return actions.PickupAction(player)


            # MULTIPLE ITEMS → OPEN MENU
            return PickupMenuHandler(self.engine)


        elif key == tcod.event.K_i:
            return InventoryActivateHandler(self.engine)
        elif key == tcod.event.K_d:
            return InventoryDropHandler(self.engine)
        elif key == tcod.event.K_c:
            return CharacterScreenEventHandler(self.engine)
        elif key == tcod.event.K_SLASH:
            return LookHandler(self.engine)

        # No valid key was pressed
        return action


class RaceSelectHandler(AskUserEventHandler):
    PADDING_X = 2
    PADDING_Y = 1
    TOP_MARGIN = 2
    DESC_GAP = 2  # gap between selection box and description box

    def __init__(self, engine, races: List[object], finish_callback: Callable[[object], object]):
        super().__init__(engine)
        self.engine = engine
        self.races = races  # list of Race dataclass instances
        self.highlight_index = 0 if races else None
        self.finish_callback = finish_callback

        # Phase: "race" first, then "subrace"
        self.phase = "race"
        self.selected_race_index: Optional[int] = None

    def on_render(self, console: tcod.Console) -> None:
        
        def format_attributes_colored(console, x, y, attrs: dict):
            """
            Print attributes with color coding:
            Positive = green
            Negative = red
            Zero = white
            """
            offset = 0
            for k, v in attrs.items():
                sign = "+" if v >= 0 else ""
                text = f"{k} {sign}{v}"

                if v > 0:
                    fg = color.green
                elif v < 0:
                    fg = color.red
                else:
                    fg = (200, 200, 200)

                console.print(x + offset, y, text, fg=fg)
                offset += len(text) + 2  # spacing between stats

    
        if not self.races:
            console.print(1, 1, "No races available.", fg=(255, 0, 0))
            return

        # Determine current list based on phase
        if self.phase == "race":
            labels = [r.name for r in self.races]
            title = "Choose Race"
        else:
            race = self.races[self.selected_race_index]
            labels = [s.name for s in getattr(race, "subraces", [])]
            title = "Choose Subrace"

        if not labels:
            labels = ["(None)"]

        box_w = max(len(l) for l in labels) + self.PADDING_X * 2 + 4
        box_h = len(labels) + self.PADDING_Y * 2 + 4

        # Center horizontally, near top with margin
        x = max(0, (console.width - box_w) // 2)
        y = self.TOP_MARGIN

        # Draw selection frame
        console.draw_frame(
            x=x,
            y=y,
            width=box_w,
            height=box_h,
            title=title,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        # Draw options
        for i, label in enumerate(labels):
            row_x = x + 2
            row_y = y + self.PADDING_Y + i + 1
            is_high = (self.highlight_index == i)
            bg = (50, 50, 150) if is_high else (0, 0, 0)
            key_char = chr(ord("a") + i)
            console.print(row_x, row_y, f"({key_char}) {label}", fg=(255, 255, 255), bg=bg)

        # Description box below
        desc_x = 2 #2 tile padding left and right
        desc_y = y + box_h + self.DESC_GAP #top padding
        desc_w = console.width - 4 #-4 for the two-tile padding on each side.
        desc_h = 10  # enough for name + description + stats

        console.draw_frame(
            x=desc_x,
            y=desc_y,
            width=desc_w,
            height=desc_h,
            title="Description",
            clear=False,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        # Fill description based on phase + highlight
        if self.phase == "race":
            race = self.races[self.highlight_index]
            console.print(desc_x + 2, desc_y + 1, race.name, fg=(200, 200, 255))
            console.print(desc_x + 2, desc_y + 2, race.description, fg=(180, 180, 180))
            
            if hasattr(race, "attributes"):
                format_attributes_colored(console, desc_x + 2, desc_y + 3, race.attributes)
        else:
            race = self.races[self.selected_race_index]
            subraces = getattr(race, "subraces", [])
            if subraces:
                sub = subraces[self.highlight_index]
                console.print(desc_x + 2, desc_y + 1, sub.name, fg=(200, 200, 255))
                console.print(desc_x + 2, desc_y + 2, sub.description, fg=(180, 180, 180))    
                
                if hasattr(sub, "attributes"):
                    format_attributes_colored(console, desc_x + 2, desc_y + 3, sub.attributes)

    def ev_keydown(self, event: tcod.event.KeyDown):
        from setup_game import MainMenu

        key = event.sym

        # Current list length
        if self.phase == "race":
            n = len(self.races)
        else:
            race = self.races[self.selected_race_index]
            n = len(getattr(race, "subraces", []))

        # Letter keys: map ONLY to current list
        if tcod.event.K_a <= key <= tcod.event.K_z:
            idx = key - tcod.event.K_a
            if 0 <= idx < n:
                self.highlight_index = idx
            return None

        # Arrow navigation within current list
        if key == tcod.event.K_UP:
            if self.highlight_index is None:
                self.highlight_index = 0
            else:
                self.highlight_index = max(0, self.highlight_index - 1)
            return None

        if key == tcod.event.K_DOWN:
            if self.highlight_index is None:
                self.highlight_index = 0
            else:
                self.highlight_index = min(n - 1, self.highlight_index + 1)
            return None

        # Enter: advance phase or confirm
        if key == tcod.event.K_RETURN:
            if self.phase == "race":
                # Lock in race, move to subrace phase (if any)
                self.selected_race_index = self.highlight_index
                race = self.races[self.selected_race_index]
                subraces = getattr(race, "subraces", [])
                if subraces:
                    self.phase = "subrace"
                    self.highlight_index = 0
                    return None
                else:
                    # No subraces: confirm with sub_idx=None
                    return self._confirm_selection(self.selected_race_index, None)
            else:
                # Subrace phase: confirm with selected subrace
                return self._confirm_selection(self.selected_race_index, self.highlight_index)

        # Escape: back to main menu
        if key == tcod.event.K_ESCAPE:
            return MainMenu()

        return None

    def _confirm_selection(self, race_idx: int, sub_idx: Optional[int]):
        from input_handlers import PopupMessage, MainGameEventHandler

        race = self.races[race_idx]
        builder = getattr(self.engine, "creation", None)
        if builder is None:
            from character_builder import CharacterBuilder
            self.engine.creation = CharacterBuilder()
            builder = self.engine.creation

        builder.race_id = race.id
        if sub_idx is not None:
            sub = race.subraces[sub_idx]
            builder.subrace_id = sub.id
        else:
            builder.subrace_id = None

        try:
            self.finish_callback(self.engine)
        except Exception as exc:
            return PopupMessage(self, f"Failed to finish creation:\n{exc}")

        return MainGameEventHandler(self.engine)


class GameOverEventHandler(EventHandler):
    def on_quit(self) -> None:
        """Handle exiting out of a finished game."""
        if os.path.exists("savegame.sav"):
            os.remove("savegame.sav")  # Deletes the active save file.
        raise exceptions.QuitWithoutSaving()  # Avoid saving a finished game.

    def ev_quit(self, event: tcod.event.Quit) -> None:
        self.on_quit()

    def ev_keydown(self, event: tcod.event.KeyDown) -> None:
        if event.sym == tcod.event.K_ESCAPE:
            self.on_quit()


CURSOR_Y_KEYS = {
    tcod.event.K_UP: -1,
    tcod.event.K_DOWN: 1,
    tcod.event.K_PAGEUP: -10,
    tcod.event.K_PAGEDOWN: 10,
}


class HistoryViewer(EventHandler):
    """Print the history on a larger window which can be navigated."""

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.log_length = len(engine.message_log.messages)
        self.cursor = self.log_length - 1

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)  # Draw the main state as the background.

        log_console = tcod.Console(console.width - 6, console.height - 6)

        # Draw a frame with a custom banner title.
        log_console.draw_frame(0, 0, log_console.width, log_console.height)
        log_console.print_box(
            0, 0, log_console.width, 1, "┤Message history├", alignment=tcod.CENTER
        )

        # Render the message log using the cursor parameter.
        self.engine.message_log.render_messages(
            log_console,
            1,
            1,
            log_console.width - 2,
            log_console.height - 2,
            self.engine.message_log.messages[: self.cursor + 1],
        )
        log_console.blit(console, 3, 3)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[MainGameEventHandler]:
        # Fancy conditional movement to make it feel right.
        if event.sym in CURSOR_Y_KEYS:
            adjust = CURSOR_Y_KEYS[event.sym]
            if adjust < 0 and self.cursor == 0:
                # Only move from the top to the bottom when you're on the edge.
                self.cursor = self.log_length - 1
            elif adjust > 0 and self.cursor == self.log_length - 1:
                # Same with bottom to top movement.
                self.cursor = 0
            else:
                # Otherwise move while staying clamped to the bounds of the history log.
                self.cursor = max(0, min(self.cursor + adjust, self.log_length - 1)) 
        elif event.sym == tcod.event.K_HOME:
            self.cursor = 0  # Move directly to the top message.
        elif event.sym == tcod.event.K_END:
            self.cursor = self.log_length - 1  # Move directly to the last message.
        else:  # Any other key moves back to the main game state.
            return MainGameEventHandler(self.engine)
        return None
