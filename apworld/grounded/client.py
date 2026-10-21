"""
The Grounded Client: a CommonClient that talks to the UE4SS mod through JSON
files in the mod's ipc/ folder (to_game.json / from_game.json, see
ARCHITECTURE.md). Registered as a Launcher Component in __init__.py so it
runs inside the installed Archipelago, frozen or not.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .grounded_data import (ITEM_ID_TO_NAME, LOCATION_ID_TO_MOD_NAME, LOCATION_ID_TO_NAME, LOCATION_NAME_TO_ID,
                            MOD_LOCATION_NAME_TO_ID)

if TYPE_CHECKING:
    pass

IPC_POLL_SECONDS = 1.0
# Recent notifications kept in to_game.json (the mod shows each once, by id).
NOTIFICATION_HISTORY = 30
# A local death this soon after a received DeathLink is that DeathLink's
# own death -- don't bounce it back out.
DEATH_LINK_GRACE_SECONDS = 10.0
# client_heartbeat.json is rewritten this often; the mod treats one older
# than 20 seconds as "the client isn't running" (ap_ipc.lua).
HEARTBEAT_SECONDS = 5.0


def _item_field(item, name: str, index: int):
    """NetworkItem fields from a PrintJSON packet, whether it arrived as a
    NetworkItem, a dict or a plain list."""
    if hasattr(item, name):
        return getattr(item, name)
    if isinstance(item, dict):
        return item.get(name)
    if isinstance(item, (list, tuple)) and len(item) > index:
        return item[index]
    return None


def _write_json_atomic(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload), encoding="utf-8")
    tmp_path.replace(path)


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Torn read racing the mod's write -- try again next poll.
        return None


def _build_context_class():
    # Built lazily: importing the apworld mustn't import CommonClient/kvui.
    from CommonClient import ClientCommandProcessor, CommonContext, logger
    from NetUtils import ClientStatus

    class GroundedCommandProcessor(ClientCommandProcessor):
        def _cmd_ipc_status(self):
            """Show the current IPC bridge state (paths, last poll)."""
            if isinstance(self.ctx, GroundedContext):
                logger.info(f"IPC dir: {self.ctx.ipc_dir}")
                logger.info(f"to_game.json: {self.ctx.to_game_path}")
                logger.info(f"from_game.json: {self.ctx.from_game_path}")
                logger.info(f"Locations sent to the server so far: {len(self.ctx.sent_location_names)}")

        def _cmd_overlay(self):
            """Turn the notification cards drawn over the game on or off."""
            if not isinstance(self.ctx, GroundedContext):
                return
            self.ctx.overlay.enabled = not self.ctx.overlay.enabled
            self.ctx.save_client_settings()
            self.ctx.write_to_game()
            logger.info("Overlay notifications " + ("on." if self.ctx.overlay.enabled else
                                                     "off -- messages show in the game's HUD instead."))

        def _cmd_override_save_binding(self):
            """Bind this server address to the save that's loaded now (e.g. after the server's port changed)."""
            if not isinstance(self.ctx, GroundedContext):
                return
            data = _read_json(self.ctx.from_game_path)
            world_name = (data or {}).get("world_name")
            world_code = (data or {}).get("world_code")
            if not world_code:
                logger.error(
                    "No world code available yet (still on the main menu?) -- can't override the "
                    "save binding until a save is loaded."
                )
                return
            server_key = self.ctx.server_address or "unknown"
            bindings = _read_json(self.ctx.save_binding_path)
            if not isinstance(bindings, dict):
                bindings = {}
            bindings[server_key] = {"name": world_name, "code": world_code}
            _write_json_atomic(self.ctx.save_binding_path, bindings)
            self.ctx.save_binding_warned = False
            logger.info(f"Rebound this multiworld session ({server_key}) to save '{world_name} - {world_code}'.")

    class GroundedContext(CommonContext):
        command_processor = GroundedCommandProcessor
        game = "Grounded"
        items_handling = 0b111  # all items, including our own and starting inventory

        def __init__(self, server_address, password, ipc_dir: Path):
            super().__init__(server_address, password)
            self.ipc_dir = ipc_dir
            self.to_game_path = ipc_dir / "to_game.json"
            self.from_game_path = ipc_dir / "from_game.json"
            self.ipc_dir.mkdir(parents=True, exist_ok=True)

            self.sent_location_names: set[str] = set()  # ones we've actually sent to the server
            self.goal_complete_sent = False
            self.slot_data: dict = {}
            self.ipc_sync_task: asyncio.Task | None = None

            # Save binding: per server address, the save's 4-character world
            # code (as in the save browser, "NEW GAME - 30EC") first seen;
            # checks from any other save are held back. /override_save_binding
            # rebinds. The code comes from location_hooks.lua's
            # refresh_world_identity.
            self.save_binding_path = ipc_dir / "save_binding.json"
            self.save_binding_warned = False

            # Notifications for the mod (_notify); ids only go up, and the
            # mod remembers the last one it showed.
            self.notifications: list[dict] = []
            self.notification_id = int(time.time())  # unique across client restarts
            # DeathLink: received deaths bump death_link_seq for the mod to
            # act on; local deaths arrive as from_game.json's death_seq.
            self.death_link_seq = 0
            self.death_link_message = ""
            self.last_game_death_seq: int | None = None
            self.room_seed_name: str | None = None
            # Overlay cards (overlay.py); /overlay toggles, saved in client_settings.json.
            from .online_data import logo_png
            from .overlay import Overlay
            self.settings_path = ipc_dir / "client_settings.json"
            self.overlay = Overlay(logo_png())
            self.overlay.enabled = bool((_read_json(self.settings_path) or {}).get("overlay", True))

        def save_client_settings(self) -> None:
            _write_json_atomic(self.settings_path, {"overlay": self.overlay.enabled})

        async def server_auth(self, password_requested: bool = False):
            if password_requested and not self.password:
                await super().server_auth(password_requested)
            await self.get_username()
            await self.send_connect()

        def on_package(self, cmd: str, args: dict):
            if cmd == "RoomInfo":
                # CommonContext doesn't store seed_name itself (needed by _room_key).
                self.room_seed_name = args.get("seed_name")
            elif cmd == "Connected":
                self.slot_data = args.get("slot_data", {})
                self._card("connected", "You have connected.", tag=False)
                asyncio.create_task(self.update_death_link(bool(self.slot_data.get("death_link"))))
                # Re-send everything after a (re)connect; the server ignores repeats.
                self.sent_location_names = set()
                self.write_to_game()
            elif cmd in ("ReceivedItems", "RoomUpdate"):
                self.write_to_game()

        # -------------------------------------------------------------
        # In-game notifications
        # -------------------------------------------------------------
        def _notify(self, text: str, detail: str = "", icon_row: str = "") -> None:
            """`text` is the headline; `detail` a second line (the in-game
            popup shows it under the headline, the feed fallback after it);
            `icon_row` an item row whose icon the in-game banner shows."""
            self.notification_id += 1
            self.notifications.append({"id": self.notification_id, "text": text, "detail": detail,
                                       "icon_row": icon_row})
            del self.notifications[:-NOTIFICATION_HISTORY]
            self.write_to_game()

        def _card(self, kind: str, title: str, subtitle: str = "", icon_png=None, tag: bool = True) -> None:
            from .overlay import Card
            try:
                self.overlay.post(Card(kind, title, subtitle, icon_png, tag))
            except Exception:
                logger.exception("Couldn't show an overlay notification")

        def _player_with_game(self, slot) -> str:
            game = getattr(self.slot_info.get(slot), "game", "") if hasattr(self, "slot_info") else ""
            return f"{self._player(slot)} ({game})" if game else self._player(slot)

        def _player(self, slot) -> str:
            return self.player_names.get(slot, f"Player {slot}")

        def _lookup(self, names, code, slot, fallback: str) -> str:
            try:
                return names.lookup_in_slot(code, slot)
            except Exception:
                # Slot info not known yet -- fine for our own game's ids.
                own = ITEM_ID_TO_NAME if names is self.item_names else LOCATION_ID_TO_NAME
                return own.get(code, fallback)

        def _location_text(self, item) -> str:
            return self._location_text_for(item.location, item.player)

        def _location_text_for(self, location, finder) -> str:
            if location is None or location < 0:
                return "Starting inventory" if location == -2 else "Cheat console"
            return self._lookup(self.location_names, location, finder, f"Location {location}")

        def on_print_json(self, args: dict):
            super().on_print_json(args)
            try:
                self._notify_from_print_json(args)
            except Exception:
                logger.exception("Couldn't turn a server message into an in-game notification")

        def _notify_from_print_json(self, args: dict) -> None:
            if self.slot is None or "item" not in args:
                return
            item = args["item"]
            item_id = _item_field(item, "item", 0)
            location_id = _item_field(item, "location", 1)
            finder = _item_field(item, "player", 2)
            receiver = args.get("receiving")
            if item_id is None or finder is None or receiver is None:
                return
            from .online_data import icon_png, item_row, location_item, own_item_icon
            from .overlay import item_kind

            item_name = self._lookup(self.item_names, item_id, receiver, f"Item {item_id}")
            flags = _item_field(item, "flags", 3) or 0
            kind = item_kind(flags)
            if args.get("type") == "ItemSend" and finder == self.slot and receiver != self.slot:
                location_name = self._lookup(self.location_names, location_id, finder, f"Location {location_id}")
                # The check's own item (e.g. "Item: Sprig" -> Sprig) shows what kind of check it was.
                checked = location_item(LOCATION_ID_TO_MOD_NAME.get(location_id, ""))
                self._notify(f"Sent {item_name} to {self._player(receiver)}", f"Location: {location_name}",
                             (checked and item_row(checked)) or "")
                self._card(kind, item_name, f"to {self._player_with_game(receiver)}  ·  {location_name}",
                           icon_png(checked) if checked else None)
            elif args.get("type") == "ItemSend" and receiver == self.slot:
                location_name = self._location_text_for(location_id, finder)
                source = "from your world" if finder == self.slot else f"from {self._player_with_game(finder)}"
                copies = sum(1 for received in self.items_received if received.item == item_id) or 1
                self._card(kind, item_name, f"{source}  ·  {location_name}", own_item_icon(item_name, copies))
            elif args.get("type") == "Hint" and not args.get("found") and self.slot in (finder, receiver):
                location_name = self._lookup(self.location_names, location_id, finder, f"Location {location_id}")
                whose = "Your" if receiver == self.slot else f"{self._player(receiver)}'s"
                where = "your world" if finder == self.slot else f"{self._player(finder)}'s world"
                self._notify(f"Hint: {whose} {item_name} is at {location_name} ({where})")
                icon = own_item_icon(item_name) if receiver == self.slot else None
                self._card("hint", item_name, f"{whose.lower() if whose == 'Your' else whose} item is at "
                                              f"{location_name} in {where}", icon)

        def on_deathlink(self, data: dict) -> None:
            super().on_deathlink(data)
            cause = data.get("cause") or f"{data.get('source', 'Someone')} died"
            self.death_link_seq += 1
            self.death_link_message = f"DeathLink: {cause}"
            self._card("deathlink", cause, "", None)
            self.write_to_game()

        def _room_key(self) -> str | None:
            """Identifies the AP room + slot the mod's saved state belongs to
            (see ap_ipc.lua's _sync_room)."""
            seed_name = self.seed_name or self.room_seed_name
            if not seed_name or self.slot is None:
                return None
            return f"{seed_name}:{self.slot}"

        def _is_connected(self) -> bool:
            return (
                self.server is not None and not self.server.socket.closed
                and self.slot is not None
            )

        # -------------------------------------------------------------
        # to_game.json: tell the mod what items have arrived
        # -------------------------------------------------------------
        def write_to_game(self):
            received_items = []
            copies: dict[str, int] = {}
            for i, item in enumerate(self.items_received):
                name = ITEM_ID_TO_NAME.get(item.item, f"Unknown Item {item.item}")
                copies[name] = copies.get(name, 0) + 1
                received_items.append({
                    "index": i,
                    "name": name,
                    # Nth copy of this item so far (progressive gear).
                    "copy": copies[name],
                    "sender": self._player(item.player) if item.player != self.slot else "",
                    # Where it was found, in the finder's world (in-game popup).
                    "location": self._location_text(item),
                })
            payload = {
                "connected": self.server is not None and not self.server.socket.closed,
                "slot": self.player_names.get(self.slot, self.auth) if self.slot else self.auth,
                "goal": (self.slot_data or {}).get("goal", 0),
                "excluded_bosses": (self.slot_data or {}).get("excluded_bosses", []),
                "received_items": received_items,
                "gold_card_drop_chance": (self.slot_data or {}).get("gold_card_drop_chance", 0),
                "gold_card_goal_amount": (self.slot_data or {}).get("gold_card_goal_amount", 65),
                "start_with_tier1_recipes": (self.slot_data or {}).get("start_with_tier1_recipes", False),
                "recipe_shuffle": (self.slot_data or {}).get("recipe_shuffle", {}),
                "creature_drop_shuffle": (self.slot_data or {}).get("creature_drop_shuffle", {}),
                "room_key": self._room_key(),
                "death_link": bool((self.slot_data or {}).get("death_link")),
                "death_link_seq": self.death_link_seq,
                "death_link_message": self.death_link_message,
                "notifications": self.notifications,
                # The client shows AP messages as overlay cards (overlay.py),
                # so the mod keeps them out of the game's HUD.
                "overlay_notifications": self.overlay.enabled,
                # Locations the server already has -- merged into the mod's
                # own state so it never re-reports or double-counts them.
                # (Under the mod's own names -- see location_renames.py.)
                "server_checked_locations": sorted(
                    LOCATION_ID_TO_MOD_NAME[loc] for loc in self.checked_locations if loc in LOCATION_ID_TO_MOD_NAME
                ),
            }
            _write_json_atomic(self.to_game_path, payload)

        # -------------------------------------------------------------
        # from_game.json: apply what the mod has reported
        # -------------------------------------------------------------
        def _check_save_binding(self, world_name, world_code) -> bool:
            """True if new checks may be sent: binds the first save seen per
            server address, then requires the same one."""
            if not world_code:
                return True  # no save loaded yet

            server_key = self.server_address or "unknown"
            bindings = _read_json(self.save_binding_path)
            if not isinstance(bindings, dict):
                bindings = {}

            existing = bindings.get(server_key)
            if existing is None:
                bindings[server_key] = {"name": world_name, "code": world_code}
                _write_json_atomic(self.save_binding_path, bindings)
                logger.info(
                    f"Bound this multiworld session ({server_key}) to save "
                    f"'{world_name} - {world_code}'. If you ever need to switch which save this is "
                    f"bound to (e.g. after the server's port changed for a long-running game), use "
                    f"/override_save_binding."
                )
                return True

            if existing.get("code") == world_code:
                return True

            if not self.save_binding_warned:
                self.save_binding_warned = True
                logger.warning(
                    f"This multiworld session ({server_key}) was bound to save "
                    f"'{existing.get('name')} - {existing.get('code')}', but the game is currently "
                    f"running save '{world_name} - {world_code}' instead. New location checks will "
                    f"NOT be sent until the original save is reloaded, to prevent progress from a "
                    f"different save being sent as checks here. If this server's port genuinely "
                    f"changed (not the save), use /override_save_binding instead."
                )
            return False

        def _itemsanity_goal_met(self) -> bool:
            """Itemsanity goal (goal 5): every "Item: " location checked on
            the server. Decided here rather than in the Lua mod, which
            can't tell itemsanity pickups from any other "Item: " report."""
            if (self.slot_data or {}).get("goal") != 5:
                return False
            # Only this seed's itemsanity checks (unticked ones in
            # location_review.txt aren't in it).
            in_seed = set(self.missing_locations) | set(self.checked_locations)
            itemsanity_ids = {i for name, i in MOD_LOCATION_NAME_TO_ID.items() if name.startswith("Item: ")} & in_seed
            return bool(itemsanity_ids) and itemsanity_ids <= set(self.checked_locations)

        async def read_from_game_and_act(self):
            data = _read_json(self.from_game_path)
            if not data:
                return

            can_send_checks = self._check_save_binding(
                data.get("world_name"), data.get("world_code")
            )

            # Only send while connected, and only reports from this room.
            if not self._is_connected() or data.get("room_key") != self._room_key():
                return

            checked_names = set(data.get("checked_locations", []))
            new_names = checked_names - self.sent_location_names
            if new_names and can_send_checks:
                ids = set()
                for name in new_names:
                    # The mod reports its own names; renamed locations
                    # (location_renames.py) have a different one in AP.
                    loc_id = MOD_LOCATION_NAME_TO_ID.get(name, LOCATION_NAME_TO_ID.get(name))
                    if loc_id is None:
                        logger.warning(f"Mod reported unknown location name '{name}', ignoring")
                        continue
                    ids.add(loc_id)
                # Leave out checks this seed doesn't have (e.g. unticked in
                # location_review.txt) -- the mod still reports them.
                in_seed = set(self.missing_locations) | set(self.checked_locations)
                if in_seed:
                    ids &= in_seed
                if ids:
                    await self.send_msgs([{"cmd": "LocationChecks", "locations": list(ids)}])
                self.sent_location_names |= new_names

            await self._handle_local_death(data.get("death_seq"))

            goal_complete = data.get("goal_complete") or self._itemsanity_goal_met()
            if goal_complete and not self.goal_complete_sent:
                self.goal_complete_sent = True
                await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                logger.info("Goal complete!")

        async def _handle_local_death(self, death_seq) -> None:
            if not isinstance(death_seq, int):
                return
            previous = self.last_game_death_seq
            self.last_game_death_seq = death_seq
            # First reading (or the game restarted and its counter reset):
            # just remember it, nothing new has happened.
            if previous is None or death_seq <= previous:
                return
            if "DeathLink" not in self.tags:
                return
            if time.time() - self.last_death_link < DEATH_LINK_GRACE_SECONDS:
                return  # this death was caused by a DeathLink we received
            await self.send_death(f"{self._player(self.slot)} didn't survive the backyard.")

        def run_gui(self):
            from kvui import GameManager

            class GroundedManager(GameManager):
                logging_pairs = [("Client", "Archipelago")]
                base_title = "Archipelago Grounded Client"

                def build(self):
                    container = super().build()
                    # Checks grouped by biome, coloured by logic (tracker_tab.py).
                    from .tracker_tab import make_tracker_view
                    self.tracker_tab = self.add_client_tab("Tracker", make_tracker_view(self.ctx))
                    # Developer-only Cheats tab, when cheats_tab.py is present
                    # (it isn't in releases or the public repository).
                    try:
                        from .cheats_tab import make_cheats_view
                    except ImportError:
                        make_cheats_view = None
                    if make_cheats_view:
                        try:
                            self.cheats_tab = self.add_client_tab("Cheats", make_cheats_view(self.ctx))
                        except Exception:
                            logger.exception("Couldn't build the Cheats tab")
                    # No Hints tab: the Tracker shows what's left and where. (kvui
                    # keeps updating its hint log in the background, harmlessly.)
                    for tab in list(self.tabs.children):
                        if getattr(tab, "text", None) == "Hints":
                            self.remove_client_tab(tab)
                    return container

            self.ui = GroundedManager(self)
            self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")
            # Make the overlay's card windows now, while the client has focus,
            # rather than on the first card mid-game.
            if self.overlay.enabled:
                self.overlay.start()

    return GroundedContext


async def _async_main(args) -> None:
    import Utils
    from CommonClient import gui_enabled, server_loop

    GroundedContext = _build_context_class()

    Utils.init_logging("GroundedClient")

    ctx = GroundedContext(args.connect, args.password, Path(args.ipc_dir))
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    ctx.ipc_sync_task = asyncio.create_task(_ipc_sync_task(ctx), name="IPCSync")

    await ctx.exit_event.wait()
    ctx.server_address = None
    await ctx.shutdown()

    if ctx.ipc_sync_task:
        await ctx.ipc_sync_task


async def _ipc_sync_task(ctx) -> None:
    from CommonClient import logger

    last_heartbeat = 0.0
    while not ctx.exit_event.is_set():
        try:
            await ctx.read_from_game_and_act()
        except Exception:
            logger.exception("Error while syncing from the game mod")
        # to_game.json only changes on events, so the mod can't tell from it
        # whether the client is still running: this file says so.
        if time.monotonic() - last_heartbeat >= HEARTBEAT_SECONDS:
            last_heartbeat = time.monotonic()
            try:
                _write_json_atomic(ctx.ipc_dir / "client_heartbeat.json",
                                   {"time": int(time.time()), "connected": ctx._is_connected()})
            except OSError:
                logger.exception("Couldn't write client_heartbeat.json")
        await asyncio.sleep(IPC_POLL_SECONDS)


def _find_grounded_ipc_dir() -> Path | None:
    """The mod's ipc/ folder in a Steam install (Steam's registry entry and
    library folders first, then common paths), or None."""
    from_registry = _find_grounded_install_via_steam_registry()
    if from_registry:
        ipc_dir = from_registry / "Maine" / "Binaries" / "Win64" / "ue4ss" / "Mods" / "GroundedArchipelago" / "ipc"
        if ipc_dir.parent.exists():  # the Mods/GroundedArchipelago folder itself, i.e. the mod is actually installed
            return ipc_dir

    common_roots = [
        r"C:\Program Files (x86)\Steam\steamapps\common\Grounded",
        r"C:\SteamLibrary\steamapps\common\Grounded",
        r"D:\SteamLibrary\steamapps\common\Grounded",
        r"D:\Steam\steamapps\common\Grounded",
        r"E:\SteamLibrary\steamapps\common\Grounded",
    ]
    for root in common_roots:
        ipc_dir = Path(root) / "Maine" / "Binaries" / "Win64" / "ue4ss" / "Mods" / "GroundedArchipelago" / "ipc"
        if ipc_dir.parent.exists():
            return ipc_dir

    return None


def _find_grounded_install_via_steam_registry() -> Path | None:
    try:
        import winreg
    except ImportError:
        return None  # not on Windows

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam") as key:
            steam_path = Path(winreg.QueryValueEx(key, "InstallPath")[0])
    except OSError:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam") as key:
                steam_path = Path(winreg.QueryValueEx(key, "InstallPath")[0])
        except OSError:
            return None

    library_folders = [steam_path]
    vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
    if vdf_path.exists():
        try:
            text = vdf_path.read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith('"path"'):
                    parts = line.split('"')
                    if len(parts) >= 4:
                        library_folders.append(Path(parts[3].replace("\\\\", "\\")))
        except OSError:
            pass

    for library in library_folders:
        candidate = library / "steamapps" / "common" / "Grounded"
        if candidate.exists():
            return candidate

    return None


def launch(*launch_args: str) -> None:
    """Entry point for the Launcher Component (and standalone runs)."""
    import colorama
    from CommonClient import get_base_parser

    parser = get_base_parser(description="Archipelago client for Grounded, bridging to a UE4SS Lua mod via files.")
    parser.add_argument(
        "--ipc-dir",
        default=None,
        help=(
            "Path to the GroundedArchipelago mod's ipc/ folder -- must match config.lua's resolved "
            "directory. If omitted, tries to auto-detect a standard Steam install first."
        ),
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Slot name to connect as. If omitted, you'll be prompted for it interactively.",
    )
    # Only what the Launcher passed: sys.argv still holds the component name
    # when started as `ArchipelagoLauncher "Grounded Client"`.
    args = parser.parse_args(list(launch_args))

    if not args.ipc_dir:
        detected = _find_grounded_ipc_dir()
        if detected:
            print(f"No --ipc-dir given; auto-detected: {detected}")
            args.ipc_dir = str(detected)
        else:
            print(
                "No --ipc-dir given, and couldn't auto-detect a standard Steam install of Grounded "
                "with the mod already present. Pass --ipc-dir explicitly this one time (check the "
                "UE4SS console/log for the exact folder the mod printed on load), or move/reinstall "
                "to a standard Steam library location and try again."
            )
            return

    colorama.just_fix_windows_console()
    asyncio.run(_async_main(args))
    colorama.deinit()
