"""Handle the loading and initialization of game sessions."""
from __future__ import annotations

import lzma
import pickle
import traceback
from typing import Optional

from data.tag_repository import TagRepository
from races import load_all_races
from character_builder import CharacterBuilder
from data_loader import DataRepository
from entity_factory import EntityFactory
from map_loader import load_map
import tcod #type: ignore

import color
from engine import Engine
from game_map import GameWorld
import input_handlers


# Load the background image and remove the alpha channel.
background_image = tcod.image.load("menu_background.png")[:, :, :3]


def prepare_new_game_engine() -> Engine:
    """
    Prepare an Engine instance for character creation.
    This sets up data repositories, the factory, and loads race data,
    but does NOT create the player or generate the map yet.
    """
    engine = Engine(player=None)

    # Data repository and factory (same as before)
    repo = DataRepository("data/actors", "data/items")
    engine.tag_repo = TagRepository("data/tags.json")
    engine.factory = EntityFactory(repo, engine)

    # Load races for character creation UI
    engine.race_catalog = load_all_races("data/races")

    # Attach an empty CharacterBuilder to hold choices during creation
    engine.creation = CharacterBuilder()

    # Message log can still be used during creation
    engine.message_log.add_message("Character creation started.", color.menu_text)

    return engine


def finish_new_game(engine: Engine) -> Engine:
    """
    After character creation completes, create the player from engine.creation,
    then generate the world and spawn them into the map.
    """
    # Create the player from the builder using your factory helper
    player = engine.factory.create_actor_from_builder(engine.creation)
    if player is None:
        raise RuntimeError("finish_new_game: factory.create_actor_from_builder returned None")
    engine.player = player

    # Now build the world / map (player exists so load_map can place it)
    txt_path = "maps/test_dungeon.txt"
    json_path = "maps/test_dungeon.json"
    engine.game_map = load_map(engine, txt_path, json_path)

    engine.game_world = GameWorld(
        engine=engine,
        max_rooms=0,
        room_min_size=0,
        room_max_size=0,
        map_width=engine.game_map.width,
        map_height=engine.game_map.height,
    )

    # Ensure player is registered with the map
    if player.parent is not engine.game_map:
        try:
            engine.game_map.entities.add(player)
        except Exception:
            pass
        player.parent = engine.game_map

    engine.update_fov()

    engine.message_log.add_message(
        "The world is ready. Press Enter to begin.", color.welcome_text
    )

    return engine




def load_game(filename: str) -> Engine:
    """Load an Engine instance from a file."""
    with open(filename, "rb") as f:
        engine = pickle.loads(lzma.decompress(f.read()))
    assert isinstance(engine, Engine)
    return engine


class MainMenu(input_handlers.BaseEventHandler):
    """Handle the main menu rendering and input."""

    def on_render(self, console: tcod.Console) -> None:
        """Render the main menu on a background image."""
        console.draw_semigraphics(background_image, 0, 0)

        console.print(
            console.width // 2,
            console.height // 2 - 4,
            "THE ARCHIVIST IS TIRED",
            fg=color.menu_title,
            alignment=tcod.CENTER,
        )
        console.print(
            console.width // 2,
            console.height - 4,
            "By Nathaniel Grimsley \n& Princess Liliana",
            fg=color.white,
            alignment=tcod.CENTER,
        )

                # --- Menu block: clear, translucent fill, colored action keys ---
        entries = ["(n)ew game", "(c)ontinue", "(q)uit"]
        menu_width = 16
        spacing = 2
        padding_top = 1
        padding_bottom = 1

        box_width = menu_width
        box_height = padding_top + padding_bottom + (len(entries) - 1) * spacing + 1

        # Position the box below the title
        title_y = console.height // 2 - 4
        box_x = (console.width - box_width) // 2
        box_y = title_y + 2

        # 1) Overwrite underlying semigraphics with real spaces so nothing bleeds through
        console.draw_rect(
            x=box_x,
            y=box_y,
            width=box_width,
            height=box_height,
            ch=ord(" "),           # overwrite glyphs with space
            fg=color.menu_text,
            bg=color.black,
        )

        # 2) Draw a translucent fill on top (ch=0 so only background blending is applied)
        console.draw_rect(
            x=box_x,
            y=box_y,
            width=box_width,
            height=box_height,
            ch=0,
            fg=color.menu_text,
            bg=color.black,
            bg_blend=tcod.BKGND_ALPHA(120),  # tweak alpha 0-255
        )

        # Helper to print an entry with a colored action key prefix like "(n)"
        def _print_menu_entry(cx: int, y: int, entry: str, key_color, text_color):
            if entry.startswith("(") and ")" in entry:
                end = entry.index(")") + 1
                key = entry[:end]
                rest = entry[end:]
            else:
                key = ""
                rest = entry
            combined = key + rest
            start_x = cx - (len(combined) // 2)
            if key:
                console.print(start_x, y, key, fg=key_color, bg=color.black)
                console.print(start_x + len(key), y, rest, fg=text_color, bg=color.black)
            else:
                console.print(start_x, y, rest, fg=text_color, bg=color.black)

        # Colors for keys
        default_key_color = color.menu_title
        quit_key_color = color.red if hasattr(color, "red") else (255, 80, 80)

        # Print each entry (no bg_blend here; the translucent layer is already drawn)
        for i, text in enumerate(entries):
            y = box_y + padding_top + i * spacing
            key_col = quit_key_color if text.lower().startswith("(q)") else default_key_color
            _print_menu_entry(box_x + box_width // 2, y, text, key_col, color.menu_text)



    def ev_keydown(
        self, event: tcod.event.KeyDown
    ) -> Optional[input_handlers.BaseEventHandler]:
        if event.sym in (tcod.event.K_q, tcod.event.K_ESCAPE):
            raise SystemExit()
        elif event.sym == tcod.event.K_c:
            try:
                return input_handlers.MainGameEventHandler(load_game("savegame.sav"))
            except FileNotFoundError:
                return input_handlers.PopupMessage(self, "No saved game to load.")
            except Exception as exc:
                traceback.print_exc()  # Print to stderr.
                return input_handlers.PopupMessage(self, f"Failed to load save:\n{exc}")
        elif event.sym == tcod.event.K_n:
            try:
                engine = prepare_new_game_engine()
                # Pass the list of Race objects and the finish callback to the handler
                races = list(engine.race_catalog.values())
                return input_handlers.RaceSelectHandler(engine, races, finish_callback=finish_new_game)
            except Exception as exc:
                traceback.print_exc()
                return input_handlers.PopupMessage(self, f"Failed to start new game:\n{exc}")


        return None
