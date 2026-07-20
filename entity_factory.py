import importlib
from entity import Actor, Item

def build_component(module: str, cls: str, args: dict):
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
            max_stack=d.get("stack_max", 1),
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
