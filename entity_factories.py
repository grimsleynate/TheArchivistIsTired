from components.ai import HostileEnemy
from components import consumable, equippable
from components.equipment import Equipment
from components.fighter import Fighter
from components.inventory import Inventory
from components.level import Level
from entity import Actor, Item

import color


player = Actor(
    char="@",
    color=color.player_color,
    name="Player",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    fighter=Fighter(hp=30, base_defense=1, base_power=2),
    inventory=Inventory(capacity=26),
    level=Level(level_up_base=200),
)

orc = Actor(
    char="o",
    color=color.common_enemy_color,
    name="Orc",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    fighter=Fighter(hp=10, base_defense=0, base_power=3),
    inventory=Inventory(capacity=0),
    level=Level(xp_given=35),
)
troll = Actor(
    char="T",
    color=color.uncommon_enemy_color,
    name="Troll",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    fighter=Fighter(hp=16, base_defense=1, base_power=4),
    inventory=Inventory(capacity=0),
    level=Level(xp_given=100),
)

confusion_scroll = Item(
    char="~",
    color=color.common_scroll_color,
    name="Confusion Scroll",
    consumable=consumable.ConfusionConsumable(number_of_turns=10),
    max_stack=99,
)
fireball_scroll = Item(
    char="~",
    color=color.common_scroll_color,
    name="Fireball Scroll",
    consumable=consumable.AreaOfEffectDamageConsumable(damage=12, radius=3),
    max_stack=99,
)
lightning_scroll = Item(
    char="~",
    color=color.common_scroll_color,
    name="Lightning Scroll",
    consumable=consumable.LightningDamageConsumable(damage=20, maximum_range=5),
    max_stack=99,
)

health_potion = Item(
    char="¿",
    color=color.common_potion_color,
    name="Health Potion",
    consumable=consumable.HealingConsumable(amount=4),
    max_stack=99,
)

dagger = Item(
    char="/", 
    color=color.common_equip_color, 
    name="Dagger", 
    equippable=equippable.Dagger(),
    max_stack=99,
)
sword = Item(
    char="/", 
    color=color.common_equip_color, 
    name="Sword", 
    equippable=equippable.Sword(),
    max_stack=99,
)

queens_staff = Item(
    char=chr(0x2320),
    color=color.rare_equip_color,
    name="The Queen's Scepter",
)

leather_armor = Item(
    char="[",
    color=color.common_equip_color,
    name="Leather Armor",
    equippable=equippable.LeatherArmor(),
    max_stack=99,
)
chain_mail = Item(
    char="[", 
    color=color.common_equip_color, 
    name="Chain Mail", 
    equippable=equippable.ChainMail(),
    max_stack=99,
)
