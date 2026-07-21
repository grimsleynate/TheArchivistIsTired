import importlib
from entity import Actor, Item
from creation_utils import compose_starting_equipment

import importlib

def build_component(module: str, cls: str, args: dict):
    if args is None:
        args = {}
    # DO NOT inject "place" into component args.
    mod = importlib.import_module(module)
    C = getattr(mod, cls)
    return C(**args)


class EntityFactory:
    def __init__(self, repo, engine):
        self.repo = repo
        self.engine = engine

    def create_item(self, item_id: str) -> Item:
        d = self.repo.get_item(item_id)

        item = Item(
            char=d["char"],
            color=tuple(d["color"]),
            name=d["name"],
            max_stack=d.get("max_stack", 1),
            description=d.get("description", "")
        )

        for comp_name, comp_def in d.get("components", {}).items():
            comp = build_component(
                comp_def["module"],
                comp_def["class"],
                comp_def.get("args", {})
            )
            setattr(item, comp_name, comp)
            comp.parent = item

        item.description = d.get("description", "")
        return item

    def create_actor(self, actor_id: str, x=0, y=0):
        d = self.repo.get_actor(actor_id)

        # Load AI class BEFORE constructing Actor
        ai_def = d.get("ai")
        if ai_def:
            ai_module = importlib.import_module(ai_def["module"])
            ai_cls = getattr(ai_module, ai_def["class"])
        else:
            ai_cls = None

        # Build components FIRST
        component_instances = {}
        
        for comp_name, comp_def in d.get("components", {}).items():
            comp = build_component(
                comp_def["module"],
                comp_def["class"],
                comp_def.get("args", {})
            )
            component_instances[comp_name] = comp

                # Ensure required components exist; fail loudly with a clear message if not.
        required = ["fighter", "inventory", "level"]
        missing = [k for k in required if component_instances.get(k) is None]
        if missing:
            raise RuntimeError(f"create_actor: missing required components {missing} for actor '{actor_id}'")

        # Construct Actor WITH components
        actor = Actor(
            char=d["char"],
            color=tuple(d["color"]),
            name=d["name"],
            ai_cls=ai_cls,
            equipment=component_instances.get("equipment"),
            fighter=component_instances.get("fighter"),
            inventory=component_instances.get("inventory"),
            level=component_instances.get("level"),
        )

        # Set parent on each component
        for comp in component_instances.values():
            comp.parent = actor

        actor.x = x
        actor.y = y

        # Starting items
        for entry in d.get("starting_items", []):
            for _ in range(entry["count"]):
                item = self.create_item(entry["item_id"])
                actor.inventory.add_item(item)
                if entry.get("equip"):
                    actor.inventory.ensure_single_item_stack(item)
                    actor.equipment.toggle_equip(item, add_message=False)

        return actor

    def create_actor_from_builder(self, builder):
        """
        Build the player Actor from the CharacterBuilder data.
        Resolves race/subrace/class from engine catalogs, composes starting equipment,
        adds items to inventory, and attempts auto-equip where requested.
        """
        if builder is None:
            raise RuntimeError("create_actor_from_builder: builder is None")

        # Create base player actor from template
        player = self.create_actor("actor.player")
        if player is None:
            raise RuntimeError("create_actor_from_builder: failed to create base player actor")

        # Resolve race object from builder.race_id (if present)
        race = None
        race_id = getattr(builder, "race_id", None)
        if race_id:
            race = getattr(self.engine, "race_catalog", {}).get(race_id)
            if race is None:
                # Not fatal: warn and continue with no race
                print(f"create_actor_from_builder: warning - unknown race_id '{race_id}'")
        else:
            # No race selected; continue (compose helper will handle None)
            race = None

        # Resolve subrace object from builder.subrace_id (if present)
        sub = None
        sub_id = getattr(builder, "subrace_id", None)
        if sub_id and race is not None:
            # race.subraces may be a list of dicts or objects; try both
            candidates = getattr(race, "subraces", []) or []
            for s in candidates:
                sid = None
                if isinstance(s, dict):
                    sid = s.get("id")
                else:
                    sid = getattr(s, "id", None)
                if sid == sub_id:
                    sub = s
                    break
            if sub is None:
                print(f"create_actor_from_builder: warning - unknown subrace_id '{sub_id}' for race '{race_id}'")

        # Resolve class object if builder provides a class id (optional)
        cls_obj = None
        cls_id = getattr(builder, "class_id", None)
        if cls_id:
            cls_obj = getattr(self.engine, "class_catalog", {}).get(cls_id)
            if cls_obj is None:
                print(f"create_actor_from_builder: warning - unknown class_id '{cls_id}'")

        # Compose final starting equipment list (deduped, ordered)
        try:
            starting_entries = compose_starting_equipment(race, sub, cls_obj)
        except Exception:
            # If compose helper expects different shapes, fall back to race-only list
            starting_entries = []
            if race and getattr(race, "starting_equipment", None):
                starting_entries.extend(race.starting_equipment)
            if sub and getattr(sub, "starting_equipment", None):
                starting_entries.extend(sub.starting_equipment)

        # starting_entries may be a list of item ids (strings) or dicts depending on your helper
        # Normalize to a list of dicts: { "item_id": str, "equip": bool, "count": int }
        normalized = []
        for e in starting_entries:
            if isinstance(e, str):
                normalized.append({"item_id": e, "equip": False, "count": 1})
            elif isinstance(e, dict):
                normalized.append({
                    "item_id": e.get("item_id"),
                    "equip": bool(e.get("equip", False)),
                    "count": int(e.get("count", 1))
                })
            else:
                # ignore unknown shapes
                continue

        # Add each item and attempt auto-equip if requested or if item has starting_item tag
        for entry in normalized:
            item_id = entry.get("item_id")
            equip = entry.get("equip", False)
            count = entry.get("count", 1)
            if not item_id:
                continue

            for _ in range(max(1, int(count))):
                try:
                    item = self.create_item(item_id)
                except Exception as exc:
                    print(f"create_actor_from_builder: failed to create item '{item_id}': {exc}")
                    continue

                # Add to inventory (ensure inventory exists)
                try:
                    player.inventory.add_item(item)
                except Exception:
                    # If inventory missing or add fails, still continue
                    print(f"create_actor_from_builder: warning - failed to add '{item_id}' to inventory")

                # Decide whether to auto-equip: explicit equip flag OR item tagged as starting_item
                should_equip = equip or ("starting_item" in getattr(item, "tags", []))

                if should_equip and getattr(player, "equipment", None):
                    # Ensure single stack if inventory supports it
                    try:
                        player.inventory.ensure_single_item_stack(item)
                    except Exception:
                        pass

                    # Try to equip using Equipment.equip (preferred)
                    try:
                        equipped = player.equipment.equip(item, actor=player, add_message=False)
                    except TypeError:
                        # Older signature: try without actor
                        try:
                            equipped = player.equipment.equip(item, add_message=False)
                        except Exception:
                            equipped = False
                    except Exception:
                        equipped = False

                    # Fallback to toggle_equip if equip returned False and toggle exists
                    if not equipped:
                        try:
                            if getattr(player, "equipment", None) and hasattr(player.equipment, "toggle_equip"):
                                player.equipment.toggle_equip(item, actor=player, add_message=False)
                        except Exception:
                            pass

        # ---- Determine spawn location safely ----
        spawn_x = spawn_y = None
        loc = getattr(builder, "starting_location", None)
        if loc:
            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                spawn_x, spawn_y = int(loc[0]), int(loc[1])
            elif isinstance(loc, dict) and "x" in loc and "y" in loc:
                spawn_x, spawn_y = int(loc["x"]), int(loc["y"])
            else:
                print("create_actor_from_builder: unrecognized starting_location:", loc)

        if spawn_x is None or spawn_y is None:
            if getattr(self.engine, "game_map", None):
                spawn_x = self.engine.game_map.width // 2
                spawn_y = self.engine.game_map.height // 2
            else:
                spawn_x, spawn_y = 0, 0

        player.x = spawn_x
        player.y = spawn_y

        # --- Apply race/subrace metadata to player (keep references for UI and logic) ---
        player.race = race
        player.subrace = sub
        player.class_obj = cls_obj

        # Merge tags from race and subrace (preserve order, dedupe)
        race_tags = list(getattr(race, "tags", []) or [])
        subrace_tags = list(getattr(sub, "tags", []) or [])
        existing_tags = list(getattr(player, "tags", []) or [])
        # preserve order and dedupe: race -> subrace -> existing
        merged = list(dict.fromkeys(race_tags + subrace_tags + existing_tags))
        player.tags = merged

        # --- Compute and store composed base attributes and proficiencies on the player ---
        # Raw base attributes (actor template) or defaults (10)
        raw_base = getattr(player, "base_attributes", {}) or {}
        STAT_ORDER = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

        def _mods_from(src):
            if not src:
                return {}
            if isinstance(src, dict):
                return {k: int(v) for k, v in (src.get("attributes", {}) or {}).items()}
            return getattr(src, "attributes", {}) or {}

        race_mods = _mods_from(race)
        subrace_mods = _mods_from(sub)
        class_mods = _mods_from(cls_obj)

        composed = {}
        for stat in STAT_ORDER:
            base_raw = int(raw_base.get(stat, 10))  # default 10 if not present
            add_race = int(race_mods.get(stat, 0))
            add_subrace = int(subrace_mods.get(stat, 0))
            add_class = int(class_mods.get(stat, 0))
            composed_value = base_raw + add_race + add_subrace + add_class
            composed[stat] = composed_value

        # Attach composed base attributes to player (single source of truth)
        player.composed_base_attributes = composed

        # Compute proficiencies using (stat - 10) // 2, allowing negative values
        profs = {}
        for stat, val in composed.items():
            try:
                profs[stat] = int((int(val) - 10) // 2)
            except Exception:
                profs[stat] = 0
        player.proficiencies = profs

        # Debug and safety: ensure we actually have an Actor
        from entity import Actor as _Actor
        print("DEBUG create_actor_from_builder: created", type(player).__name__, "coords", (player.x, player.y))
        if not isinstance(player, _Actor):
            raise RuntimeError(f"create_actor_from_builder: factory returned {type(player).__name__} instead of Actor")

        return player
