from __future__ import annotations

import lzma
import pickle
from typing import TYPE_CHECKING

import pygame #type: ignore
from enum import Enum
from rendering.tileset_manager import TileSetManager
from rendering.pygame_render import render_all as pygame_render_all

from tcod.console import Console #type: ignore
from tcod.map import compute_fov #type: ignore

import exceptions
from message_log import MessageLog
import render_functions

if TYPE_CHECKING:
    from entity import Actor
    from game_map import GameMap, GameWorld


class RenderMode(Enum):
    GLYPH = 1
    TILE = 2


class Engine:
    game_map: GameMap
    game_world: GameWorld

    def __init__(self, player: Actor):
        self.message_log = MessageLog()
        self.mouse_location = (0, 0)
        self.player = player
        self.screen = None
        self.clock = None
        self.tile_size = 16
        self.tileset_manager = TileSetManager()
        self.render_mode = RenderMode.GLYPH

        # internal: mark FOV dirty when player moves
        self._fov_dirty = True

    def handle_enemy_turns(self) -> None:
        for entity in set(self.game_map.actors) - {self.player}:
            if entity.ai:
                try:
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass  # Ignore impossible action exceptions from AI.

    def update_fov(self) -> None:
        """Recompute the visible area based on the players point of view."""
        self.game_map.visible[:] = compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius=8,
        )
        # If a tile is "visible" it should be added to "explored".
        self.game_map.explored |= self.game_map.visible
        
        # --- Pygame / tileset helpers (add these) ---
    def init_tilesets(self, mapping: dict) -> None:
        """
        mapping: dict of name -> path
        Example: {"tiles":"data/tiles.png", "creatures":"data/creatures.png"}
        """
        for name, path in mapping.items():
            try:
                self.tileset_manager.load(name, path, self.tile_size)
            except Exception as e:
                # do not crash; print warning
                print(f"Failed to load tileset {name} from {path}: {e}")

    def toggle_render_mode(self) -> None:
        if self.render_mode == RenderMode.GLYPH:
            # only switch to TILE if at least one tileset loaded
            if any(self.tileset_manager.has(k) for k in ["tiles", "creatures", "rogues", "items"]):
                self.render_mode = RenderMode.TILE
        else:
            self.render_mode = RenderMode.GLYPH

    def mark_fov_dirty(self) -> None:
        self._fov_dirty = True

    def update_fov_if_needed(self) -> None:
        """
        Call the tutorial's FOV update routine if the map exposes one.
        This preserves existing tutorial behavior.
        """
        if not getattr(self, "_fov_dirty", False):
            return

        # Prefer game_map.compute_fov(player.x, player.y) if present
        gm = getattr(self, "game_map", None)
        player = getattr(self, "player", None)
        if gm is None or player is None:
            self._fov_dirty = False
            return

        if hasattr(gm, "compute_fov"):
            try:
                gm.compute_fov(player.x, player.y)
            except TypeError:
                # some implementations expect no args
                gm.compute_fov()
        elif hasattr(gm, "update_fov"):
            try:
                gm.update_fov(player.x, player.y)
            except TypeError:
                gm.update_fov()
        # else: nothing to call

        self._fov_dirty = False


    def render(self, console: Console) -> None:
        self.game_map.render(console)

        self.message_log.render(console=console, x=21, y=45, width=40, height=5)

        render_functions.render_bar(
            console=console,
            current_value=self.player.fighter.hp,
            maximum_value=self.player.fighter.max_hp,
            total_width=20,
        )

        render_functions.render_dungeon_level(
            console=console,
            dungeon_level=self.game_world.current_floor,
            location=(0, 47),
        )

        render_functions.render_names_at_mouse_location(
            console=console, x=21, y=44, engine=self
        )

    def save_as(self, filename: str) -> None:
        """Save this Engine instance as a compressed file."""
        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)
