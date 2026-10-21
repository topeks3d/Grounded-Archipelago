"""
The Grounded Client's "Tracker" tab: a sidebar (Overview, Map, regions,
craft groups, other check kinds) and the selected tab's checks, each in
logic / out of logic / checked, clickable for an info popup.

Logic is rules.location_rules evaluated against a stand-in state built from
the items received, so it matches generation. The map's "visited" also uses
the mod's own reports (from_game.json), so it works with Landmark Checks off.

build_groups() / landmark_map() are plain Python (tested); Kivy is only
imported inside make_tracker_view().
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from .gear import PROGRESSIVE_LINES
from .grounded_data import ITEM_ID_TO_NAME, LOCATION_ID_TO_MOD_NAME, LOCATION_ID_TO_NAME
from .landmarks import LANDMARK_PREFIX, landmark_location_names
from .location_renames import ap_name
from .review_data import CRAFT_GROUPS, DISABLED_LOCATIONS, LOCATION_BIOMES, REGIONS

CHECKED, IN_LOGIC, OUT_OF_LOGIC = "checked", "logic", "out"
VISITED = "visited"

# Non-biome groups, shown after the biomes, by location name prefix.
_KIND_GROUPS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Bosses", ("Kill: ", "Defeat ", "Go Big")),
    ("Gold Cards", ("Gold Card: ",)),
    ("Molars", ("Molars: ",)),
    ("Mutations", ("Mutations: ",)),
)
OTHER_GROUPS: List[str] = [name for name, _ in _KIND_GROUPS] + ["Other"]
GROUP_ORDER: List[str] = list(REGIONS) + list(CRAFT_GROUPS) + OTHER_GROUPS

# Kind of check (sections inside a tab), by the mod's name prefix.
_KINDS: Tuple[Tuple[str, str], ...] = (
    ("Item: ", "Items"), ("Craft: ", "Crafting"), (LANDMARK_PREFIX, "Landmarks"),
    ("Kill: ", "Bosses"), ("Defeat ", "Bosses"), ("Go Big", "Bosses"),
    ("Gold Card: ", "Gold Cards"), ("Molars: ", "Molars"), ("Mutations: ", "Mutations"),
)
KIND_ORDER: List[str] = ["Items", "Crafting", "Landmarks", "Bosses", "Gold Cards", "Molars", "Mutations", "Other"]
# Name prefixes left out under their own section heading.
_SECTION_PREFIXES: Dict[str, Tuple[str, ...]] = {
    "Items": ("Item: ",), "Crafting": ("Craft: ", "Cook: "), "Landmarks": (LANDMARK_PREFIX,),
}


class Check(NamedTuple):
    name: str       # as Archipelago shows it
    status: str     # CHECKED / IN_LOGIC / OUT_OF_LOGIC
    kind: str = "Other"
    mod_name: str = ""


class Landmark(NamedTuple):
    name: str       # as Archipelago shows it, without "Landmark: "
    status: str     # VISITED / IN_LOGIC / OUT_OF_LOGIC
    mod_name: str = ""
    region: str = ""


class _ItemState:
    """Just enough of CollectionState for rules.py's rules."""

    def __init__(self, counts: Counter):
        self.counts = counts

    def has(self, name: str, player: int, count: int = 1) -> bool:
        return self.counts[name] >= count

    def has_any(self, names: Iterable[str], player: int) -> bool:
        return any(self.counts[name] > 0 for name in names)

    def has_all(self, names: Iterable[str], player: int) -> bool:
        return all(self.counts[name] > 0 for name in names)

    def count(self, name: str, player: int) -> int:
        return self.counts[name]


def item_counts(item_names: Iterable[str]) -> Counter:
    """Received item names -> counts, crediting ProgressiveGear the way
    GroundedWorld.collect does (the Nth copy also gives the Nth gear piece)."""
    counts: Counter = Counter()
    for name in item_names:
        counts[name] += 1
        line = PROGRESSIVE_LINES.get(name)
        if line and counts[name] <= len(line):
            counts[line[counts[name] - 1]] += 1
    return counts


def group_of(mod_name: str) -> str:
    biome = LOCATION_BIOMES.get(mod_name)
    if biome:
        return biome
    for group, prefixes in _KIND_GROUPS:
        if mod_name.startswith(prefixes):
            return group
    return "Other"


def kind_of(mod_name: str) -> str:
    for prefix, kind in _KINDS:
        if mod_name.startswith(prefix):
            return kind
    return "Other"


_rules_cache: Dict[tuple, dict] = {}


def _rules_for(slot_data: dict) -> dict:
    from .rules import location_rules

    key = (tuple(sorted(slot_data.get("excluded_bosses") or ())),
           tuple(sorted(slot_data.get("recipe_shuffle") or {})))
    if key not in _rules_cache:
        _rules_cache.clear()
        _rules_cache[key] = location_rules(set(key[0]), frozenset(key[1]))
    return _rules_cache[key]


def state_for(received_item_ids: Iterable[int]) -> _ItemState:
    return _ItemState(item_counts(ITEM_ID_TO_NAME.get(i, "") for i in received_item_ids))


def _in_logic(rules: dict, mod_name: str, state: _ItemState) -> bool:
    rule = rules.get(mod_name)
    return rule is None or rule(state, 1)


def build_groups(location_ids: Iterable[int], checked_ids: Iterable[int], received_item_ids: Iterable[int],
                 slot_data: Optional[dict]) -> List[Tuple[str, List[Check]]]:
    """[(group name, [Check, ...]), ...] in display order, empty groups left out."""
    rules = _rules_for(slot_data or {})
    state = state_for(received_item_ids)
    checked = set(checked_ids)
    groups: Dict[str, List[Check]] = {}
    for loc_id in sorted(set(location_ids)):
        mod_name = LOCATION_ID_TO_MOD_NAME.get(loc_id)
        if mod_name is None:
            continue
        if loc_id in checked:
            status = CHECKED
        else:
            status = IN_LOGIC if _in_logic(rules, mod_name, state) else OUT_OF_LOGIC
        check = Check(LOCATION_ID_TO_NAME.get(loc_id, mod_name), status, kind_of(mod_name), mod_name)
        groups.setdefault(group_of(mod_name), []).append(check)
    order = {status: i for i, status in enumerate((IN_LOGIC, OUT_OF_LOGIC, CHECKED))}
    return [(group, sorted(groups[group], key=lambda c: (order[c.status], c.name)))
            for group in GROUP_ORDER if group in groups]


def landmark_map(visited_mod_names: Iterable[str], received_item_ids: Iterable[int],
                 slot_data: Optional[dict]) -> List[Tuple[str, List[Landmark]]]:
    """[(region, [Landmark, ...]), ...] for every landmark ticked in the
    review file, in REGIONS order. Works whether or not the seed has
    Landmark Checks on."""
    rules = _rules_for(slot_data or {})
    state = state_for(received_item_ids)
    visited = set(visited_mod_names)
    regions: Dict[str, List[Landmark]] = {}
    for mod_name in landmark_location_names:
        if mod_name in DISABLED_LOCATIONS:
            continue
        if mod_name in visited:
            status = VISITED
        else:
            status = IN_LOGIC if _in_logic(rules, mod_name, state) else OUT_OF_LOGIC
        name = ap_name(mod_name)
        if name.startswith(LANDMARK_PREFIX):
            name = name[len(LANDMARK_PREFIX):]
        region = LOCATION_BIOMES.get(mod_name, "Other")
        regions.setdefault(region, []).append(Landmark(name, status, mod_name, region))
    order = list(REGIONS) + ["Other"]
    return [(region, sorted(regions[region], key=lambda l: l.name)) for region in order if region in regions]


# ---------------------------------------------------------------------------
# Kivy view
# ---------------------------------------------------------------------------
_COLOURS = {IN_LOGIC: "4caf50", OUT_OF_LOGIC: "e57373", CHECKED: "8a8a8a", VISITED: "4caf50"}
_STATUS_TEXT = {IN_LOGIC: "In logic", OUT_OF_LOGIC: "Not in logic yet", CHECKED: "Checked", VISITED: "Visited"}
_PIN_RGB = {VISITED: (0.30, 0.69, 0.31), IN_LOGIC: (0.95, 0.95, 0.95), OUT_OF_LOGIC: (0.90, 0.45, 0.45)}
_STATUS_RGB = {IN_LOGIC: (0.40, 0.78, 0.42), OUT_OF_LOGIC: (0.93, 0.50, 0.47), CHECKED: (0.60, 0.63, 0.67),
               VISITED: (0.40, 0.78, 0.42)}
_CHIP_TEXT = {IN_LOGIC: "Ready", OUT_OF_LOGIC: "Locked", CHECKED: "Done"}
# Material Design icon per section / check kind (KivyMD's icon font).
_KIND_ICONS = {"Items": "hand-back-left-outline", "Crafting": "hammer-wrench", "Landmarks": "map-marker-outline",
               "Bosses": "sword-cross", "Gold Cards": "cards-outline", "Molars": "tooth-outline",
               "Mutations": "dna", "Other": "star-four-points-outline"}
# KivyMD's bundled Material Design icon font.
_ICON_FONT = "[font=Icons]{}[/font]"
_TICK, _CROSS, _CIRCLE = "\U000f012c", "\U000f0156", "\U000f0766"


def _from_game(ctx) -> dict:
    path = getattr(ctx, "from_game_path", None)
    if not path:
        return {}
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _visited_from_mod(data: dict) -> set:
    """Landmarks the mod has reported (from_game.json), checks or not."""
    names = data.get("checked_locations") or []
    return {name for name in names if isinstance(name, str) and name.startswith(LANDMARK_PREFIX)}


def make_tracker_view(ctx):
    """The tab's root widget. Refreshes itself once a second when anything
    it shows has changed."""
    import io

    from kivy.clock import Clock
    from kivy.core.image import Image as CoreImage
    from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
    from kivy.graphics.transformation import Matrix
    from kivy.metrics import dp, sp
    from kivy.uix.label import Label
    from kivy.uix.behaviors import ButtonBehavior
    from kivy.uix.image import Image
    from kivy.uix.modalview import ModalView
    from kivy.uix.relativelayout import RelativeLayout
    from kivy.uix.scatter import Scatter
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.stencilview import StencilView
    from kivy.uix.widget import Widget
    from kivy.utils import escape_markup
    from kivymd.app import MDApp
    from kivymd.uix.boxlayout import MDBoxLayout
    from kivymd.uix.button import MDButton, MDButtonText
    from kivymd.uix.gridlayout import MDGridLayout
    from kivy.core.window import Window
    from kivymd.icon_definitions import md_icons
    from kivymd.uix.behaviors import HoverBehavior
    from kivymd.uix.label import MDLabel

    from . import online_data

    def md_icon(name: str) -> str:
        return md_icons.get(name, "")

    theme = MDApp.get_running_app().theme_cls

    def theme_colour(name: str, fallback):
        return list(getattr(theme, name, None) or fallback)

    def label(text: str, style="Body", role="medium", **kwargs) -> MDLabel:
        """A markup label that grows to fit its wrapped text."""
        widget = MDLabel(text=text, markup=True, font_style=style, role=role, size_hint_y=None, height=0, **kwargs)
        widget.bind(width=lambda inst, width: setattr(inst, "text_size", (width, None)))
        widget.bind(texture_size=lambda inst, size: setattr(inst, "height", size[1]))
        return widget

    def paint(widget, rgba, radius=8):
        """Rounded background that follows the widget."""
        with widget.canvas.before:
            colour = Color(*rgba)
            rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(radius)])
        widget.bind(pos=lambda inst, pos: setattr(rect, "pos", pos),
                    size=lambda inst, size: setattr(rect, "size", size))
        return colour

    textures: Dict[str, object] = {}

    def texture(key: str, data: Optional[bytes]):
        if key not in textures:
            textures[key] = CoreImage(io.BytesIO(data), ext="png").texture if data else None
        return textures[key]

    def kind_icon(check: Check, size: float) -> Widget:
        """The item's own icon for items / crafts, otherwise a symbol."""
        if check.kind in ("Items", "Crafting"):
            item = check.mod_name.split(": ", 1)[-1]
            if online_data.icon_png(item):
                return icon_widget(item, size)
        glyph = md_icon(_KIND_ICONS.get(check.kind, "star-four-points-outline"))
        return Label(text=_ICON_FONT.format(glyph), markup=True, size_hint_x=None, width=size, font_size=sp(22),
                     color=(0.75, 0.80, 0.86, 1))

    def icon_widget(name: str, size: float) -> Widget:
        tex = texture("icon:" + name, online_data.icon_png(name))
        if tex is None:
            return Widget(size_hint=(None, None), size=(size, size))
        return Image(texture=tex, size_hint=(None, None), size=(size, size), fit_mode="contain")

    # -- popups --------------------------------------------------------------
    def popup(build) -> None:
        view = ModalView(size_hint=(None, None), width=dp(470), background_color=(0, 0, 0, 0.55),
                         overlay_color=(0, 0, 0, 0.45))
        card = MDBoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10), size_hint_y=None)
        card.bind(minimum_height=card.setter("height"))
        paint(card, theme_colour("surfaceContainerHighColor", (0.18, 0.18, 0.2, 1)), radius=14)
        build(card)
        card.bind(height=lambda inst, height: setattr(view, "height", height))
        view.add_widget(card)
        view.open()

    def header(card, icon_name: Optional[str], title: str, subtitle: str):
        row = MDBoxLayout(orientation="horizontal", spacing=dp(12), size_hint_y=None, height=dp(64))
        if icon_name:
            row.add_widget(icon_widget(icon_name, dp(64)))
        text = MDBoxLayout(orientation="vertical", spacing=dp(2))
        text.add_widget(Widget())
        text.add_widget(label(f"[b]{escape_markup(title)}[/b]", style="Title", role="medium"))
        text.add_widget(label(subtitle, role="small"))
        text.add_widget(Widget())
        row.add_widget(text)
        card.add_widget(row)

    def requirement_lines(requirements) -> str:
        if not requirements:
            return f"[color={_COLOURS[IN_LOGIC]}]{_ICON_FONT.format(_TICK)}  Nothing[/color]"
        lines = []
        for req in requirements:
            colour = _COLOURS[IN_LOGIC] if req.met else _COLOURS[OUT_OF_LOGIC]
            mark = _ICON_FONT.format(_TICK if req.met else _CROSS)
            lines.append(f"[color={colour}]{mark}  {escape_markup(req.text)}[/color]")
        return "\n".join(lines)

    def section(card, title: str):
        card.add_widget(label(f"[b]{title}[/b]", style="Title", role="small"))

    def show_check_info(check: Check, view) -> None:
        info = online_data.check_info(check.mod_name, check.name, view.state, view.slot_data, view.recipe_slots)

        def build(card):
            header(card, info.item if info.kind in ("Item", "Craft") else None, info.title,
                   f"[color={_COLOURS[check.status]}]{_STATUS_TEXT[check.status]}[/color]   {info.kind}")
            section(card, "Needs")
            card.add_widget(label(requirement_lines(info.requirements)))
            if info.sources:
                pin = _ICON_FONT.format(md_icon("map-marker-outline"))
                section(card, "Where to find it" + ("   [size=12sp][color=ffb74d]shuffled drops this seed[/color][/size]"
                                                     if info.sources_shuffled else ""))
                card.add_widget(label("\n".join(f"{pin}  {escape_markup(line)}" for line in info.sources)))
            elif info.sources_shuffled:
                section(card, "Where to find it")
                card.add_widget(label("[color=ffb74d]No creature drops it this seed (Creature Drop Shuffle).[/color]"))
            for recipe in info.recipes:
                title = "Recipe" + (" (shuffled)" if recipe.shuffled else "")
                section(card, title + (f"   [size=12sp]{escape_markup(recipe.station)}[/size]" if recipe.station else ""))
                grid = MDGridLayout(cols=2, size_hint_y=None, spacing=(dp(8), dp(4)), adaptive_height=True)
                for name, count in recipe.materials:
                    cell = MDBoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(32))
                    cell.add_widget(icon_widget(name, dp(32)))
                    cell.add_widget(MDLabel(text=f"{count} x {escape_markup(str(name))}", markup=True,
                                            font_style="Body", role="medium"))
                    grid.add_widget(cell)
                card.add_widget(grid)
            if info.kind in ("Item", "Craft") and not info.recipes:
                card.add_widget(label("[color=9aa3ad]No recipe -- found in the world.[/color]"
                                      if info.kind == "Item" else "[color=9aa3ad]No recipe data.[/color]"))
            if info.note:
                card.add_widget(label(f"[size=12sp][color=9aa3ad]{escape_markup(info.note)}[/color][/size]"))

        popup(build)

    def show_landmark_info(mark: Landmark, view) -> None:
        info = online_data.check_info(mark.mod_name, LANDMARK_PREFIX + mark.name, view.state, view.slot_data)
        pin = online_data.landmark_pins().get(mark.mod_name[len(LANDMARK_PREFIX):], {})

        def build(card):
            header(card, None, mark.name,
                   f"[color={_COLOURS[mark.status]}]{_STATUS_TEXT[mark.status]}[/color]   {escape_markup(mark.region)}")
            section(card, "Needs")
            card.add_widget(label(requirement_lines(info.requirements)))
            notes = [info.note] if info.note else []
            if pin.get("title") and pin["title"] != mark.name:
                notes.append(f"On the map as \"{pin['title']}\".")
            notes.append(f"Game name: {mark.mod_name[len(LANDMARK_PREFIX):]}")
            card.add_widget(label("[size=12sp][color=9aa3ad]" + escape_markup("\n".join(notes)) + "[/color][/size]"))

        popup(build)

    # -- widgets ---------------------------------------------------------------
    class CheckProgressBar(Widget):
        """Thin bar: checked (primary) then in logic (green) out of total."""

        def __init__(self, done: int, in_logic: int, total: int, **kwargs):
            super().__init__(size_hint_y=None, height=dp(6), **kwargs)
            self.parts = (done, in_logic, total)
            self.bind(pos=self.redraw, size=self.redraw)

        def redraw(self, *_args):
            done, in_logic, total = self.parts
            self.canvas.clear()
            with self.canvas:
                Color(1, 1, 1, 0.10)
                RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(3)])
                if total:
                    done_w = self.width * done / total
                    logic_w = self.width * in_logic / total
                    Color(*theme_colour("primaryColor", (0.6, 0.7, 0.85, 1)))
                    Rectangle(pos=self.pos, size=(done_w, self.height))
                    Color(0.30, 0.69, 0.31, 0.85)
                    Rectangle(pos=(self.x + done_w, self.y), size=(logic_w, self.height))

    class SideRow(ButtonBehavior, MDBoxLayout):
        """One tab in the sidebar: name, counts and a progress bar."""

        def __init__(self, tab: str, view, **kwargs):
            super().__init__(orientation="vertical", size_hint_y=None, padding=(dp(10), dp(6)),
                             spacing=dp(3), **kwargs)
            self.tab, self.view = tab, view
            self.bind(minimum_height=self.setter("height"))
            self.bg = paint(self, (0, 0, 0, 0))
            self.title = label("")
            self.add_widget(self.title)
            self.bar_slot = MDBoxLayout(size_hint_y=None, height=dp(6))
            self.add_widget(self.bar_slot)

        def update(self, title: str, done: int, in_logic: int, total: int, selected: bool):
            self.title.text = title
            self.bar_slot.clear_widgets()
            if total:
                self.bar_slot.add_widget(CheckProgressBar(done, in_logic, total))
            primary = theme_colour("primaryColor", (0.6, 0.7, 0.85, 1))
            self.bg.rgba = (primary[0], primary[1], primary[2], 0.28) if selected else (0, 0, 0, 0)

        def on_release(self):
            self.view.select(self.tab)

    class CheckTile(ButtonBehavior, HoverBehavior, MDBoxLayout):
        """One check: icon, name, a status chip and a "details" chevron.
        Lights up (with a hand cursor) under the mouse; click for the popup."""

        def __init__(self, check: Check, name: str, view, **kwargs):
            super().__init__(orientation="horizontal", size_hint_y=None, height=dp(48),
                             padding=(dp(14), dp(6), dp(10), dp(6)), spacing=dp(10), **kwargs)
            self.check, self.view = check, view
            self._hover_ready = False
            Clock.schedule_once(lambda dt: setattr(self, "_hover_ready", True), 0.25)
            colour = _STATUS_RGB[check.status]
            with self.canvas.before:
                self.bg = Color(1, 1, 1, 0.045)
                self._bg = RoundedRectangle(radius=[dp(10)])
                Color(*colour, 0.95 if check.status != CHECKED else 0.45)
                self._bar = RoundedRectangle(radius=[dp(2)])
            self.bind(pos=self._layout_bg, size=self._layout_bg)

            self.add_widget(kind_icon(check, dp(32)))
            done = check.status == CHECKED
            text = escape_markup(name)
            # Plain Kivy labels: KivyMD re-themes custom text colours on rebuilt widgets.
            title = Label(text=f"[s]{text}[/s]" if done else text, markup=True, font_size=sp(16),
                          shorten=True, shorten_from="right", halign="left", valign="middle",
                          color=(0.62, 0.64, 0.67, 1) if done else (0.94, 0.95, 0.96, 1))
            title.bind(size=lambda inst, size: setattr(inst, "text_size", size))
            self.add_widget(title)
            self.add_widget(Chip(_CHIP_TEXT[check.status], colour))
            self.chevron = Label(text=_ICON_FONT.format(md_icon("chevron-right")), markup=True, size_hint_x=None,
                                 width=dp(16), font_size=sp(18), color=(1, 1, 1, 0.35))
            self.add_widget(self.chevron)

        def _layout_bg(self, *_args):
            self._bg.pos, self._bg.size = self.pos, self.size
            self._bar.pos, self._bar.size = (self.x + dp(4), self.y + dp(9)), (dp(4), self.height - dp(18))

        def on_enter(self, *_args):
            # Freshly built tiles all sit at (0, 0) until laid out, so the
            # mouse can "enter" every one of them at once: ignore hovers
            # until the layout has settled.
            if not self._hover_ready:
                return
            self.bg.a = 0.11
            self.chevron.color = (1, 1, 1, 0.9)
            Window.set_system_cursor("hand")

        def on_leave(self, *_args):
            self.bg.a = 0.045
            self.chevron.color = (1, 1, 1, 0.35)
            Window.set_system_cursor("arrow")

        def on_release(self):
            Window.set_system_cursor("arrow")
            show_check_info(self.check, self.view)

    class Chip(Label):
        """Small rounded status label."""

        def __init__(self, text: str, rgb, **kwargs):
            super().__init__(text=text, font_size=sp(12), halign="center", valign="middle",
                             size_hint=(None, None), size=(dp(62), dp(22)), color=(*rgb, 1),
                             pos_hint={"center_y": 0.5}, **kwargs)
            with self.canvas.before:
                Color(*rgb, 0.16)
                self._rect = RoundedRectangle(radius=[dp(11)])
            self.bind(pos=self._move, size=self._move)

        def _move(self, *_args):
            self._rect.pos, self._rect.size = self.pos, self.size

    class SectionHeader(MDBoxLayout):
        """Section title with a short coloured underline and its counts."""

        def __init__(self, kind: str, done: int, ready: int, total: int, **kwargs):
            super().__init__(orientation="horizontal", size_hint_y=None, height=dp(46),
                             padding=(dp(2), dp(14), 0, dp(4)), spacing=dp(8), **kwargs)
            icon = _ICON_FONT.format(md_icon(_KIND_ICONS.get(kind, "star-four-points-outline")))
            self.add_widget(MDLabel(text=f"[size=18sp]{icon}[/size]  [b]{kind}[/b]", markup=True, font_style="Title",
                                    role="medium", size_hint_x=None, width=dp(190)))
            counts = f"{done} of {total} done" + (f"    [color={_COLOURS[IN_LOGIC]}]{ready} ready[/color]" if ready else "")
            self.add_widget(MDLabel(text=f"[color=9aa3ad]{counts}[/color]", markup=True, font_style="Body",
                                    role="medium"))
            primary = theme_colour("primaryColor", (0.6, 0.7, 0.85, 1))
            with self.canvas.after:
                Color(primary[0], primary[1], primary[2], 0.6)
                self._line = RoundedRectangle(radius=[dp(1)])
            self.bind(pos=self._move, size=self._move)

        def _move(self, *_args):
            self._line.pos, self._line.size = (self.x + dp(2), self.y + dp(2)), (dp(40), dp(3))

    class Pin(ButtonBehavior, Widget):
        """A landmark on the map: filled dot (a ring when its position is a
        best guess), coloured by status. Lives inside the map's Scatter (map
        pixel coordinates), so `zoom` keeps it the same size on screen."""

        def __init__(self, mark: Landmark, u: float, v: float, approx: bool, view, **kwargs):
            super().__init__(size_hint=(None, None), **kwargs)
            self.mark, self.u, self.v, self.approx, self.view = mark, u, v, approx, view
            self.zoom = 1.0
            self.bind(pos=self.redraw, size=self.redraw)

        def set_mark(self, mark: Landmark):
            self.mark = mark
            self.redraw()

        def place(self, map_size: float, zoom: float):
            self.zoom = zoom
            self.size = (dp(22) / zoom, dp(22) / zoom)
            self.center = (self.u * map_size, (1 - self.v) * map_size)

        def redraw(self, *_args):
            z = self.zoom
            r = dp(6) / z
            cx, cy = self.center
            rgb = _PIN_RGB[self.mark.status]
            self.canvas.clear()
            with self.canvas:
                Color(0, 0, 0, 0.75)
                Ellipse(pos=(cx - r - dp(2) / z, cy - r - dp(2) / z), size=(2 * r + dp(4) / z, 2 * r + dp(4) / z))
                Color(*rgb, 1)
                if self.approx:
                    Line(circle=(cx, cy, r - dp(1) / z), width=dp(2) / z)
                else:
                    Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))

        def on_release(self):
            show_landmark_info(self.mark, self.view)

    class MapScatter(Scatter):
        """Pan by dragging, zoom with the mouse wheel."""

        def on_touch_down(self, touch):
            if self.collide_point(*touch.pos) and touch.is_mouse_scrolling:
                factor = 1.15 if touch.button == "scrolldown" else 1 / 1.15
                new_scale = self.scale * factor
                if self.scale_min <= new_scale <= self.scale_max:
                    self.apply_transform(Matrix().scale(factor, factor, factor), anchor=touch.pos)
                return True
            return super().on_touch_down(touch)

    class MapView(RelativeLayout):
        def __init__(self, view, **kwargs):
            super().__init__(**kwargs)
            self.view = view
            self.pins: Dict[str, Pin] = {}
            stencil = StencilView(size_hint=(1, 1))
            self.add_widget(stencil)
            with stencil.canvas.before:
                Color(0, 0, 0, 1)
                self._bg = Rectangle(pos=(0, 0), size=self.size)
            self.bind(size=lambda inst, size: setattr(self._bg, "size", size))
            tex = texture("map", online_data.map_png())
            self.map_size = tex.width if tex else 1024
            self.scatter = MapScatter(do_rotation=False, size=(self.map_size, self.map_size),
                                      size_hint=(None, None), scale_min=0.05, scale_max=4, auto_bring_to_front=False)
            if tex:
                self.scatter.add_widget(Image(texture=tex, size=(self.map_size, self.map_size),
                                              size_hint=(None, None), fit_mode="fill"))
            stencil.add_widget(self.scatter)
            self.scatter.bind(scale=self.place_pins)
            self.bind(size=lambda *_: self.reset())
            self.hidden = set()

        def reset(self):
            if not self.width or not self.height:
                return
            scale = min(self.width, self.height) / self.map_size
            self.scatter.scale_min = scale * 0.8
            self.scatter.transform = Matrix().scale(scale, scale, scale)
            self.scatter.pos = ((self.width - self.map_size * scale) / 2, (self.height - self.map_size * scale) / 2)
            self.place_pins()

        def update(self, landmarks: List[Tuple[str, List[Landmark]]], hide_visited: bool, logic_only: bool):
            pins = online_data.landmark_pins()
            for _region, marks in landmarks:
                for mark in marks:
                    asset = mark.mod_name[len(LANDMARK_PREFIX):]
                    if asset not in pins:
                        continue
                    pin = self.pins.get(asset)
                    if pin is None:
                        entry = pins[asset]
                        pin = Pin(mark, entry["u"], entry["v"], entry.get("approx", False), self.view)
                        self.pins[asset] = pin
                    elif pin.mark != mark:
                        pin.set_mark(mark)
                    hide = (hide_visited and mark.status == VISITED) or (logic_only and mark.status != IN_LOGIC)
                    if hide and pin.parent:
                        self.scatter.remove_widget(pin)
                    elif not hide and not pin.parent:
                        self.scatter.add_widget(pin)
            self.place_pins()

        def place_pins(self, *_args):
            for pin in self.pins.values():
                pin.place(self.map_size, self.scatter.scale)

    class TrackerView(MDBoxLayout):
        def __init__(self, **kwargs):
            super().__init__(orientation="horizontal", padding=dp(6), spacing=dp(8), **kwargs)
            self.hide_checked = False
            self.logic_only = False
            self.selected = "Overview"
            self._signature = None
            self._groups: List[Tuple[str, List[Check]]] = []
            self._landmarks: List[Tuple[str, List[Landmark]]] = []
            self._rows: Dict[str, tuple] = {}
            self._map: Optional[MapView] = None
            self.state = state_for(())
            self.slot_data: dict = {}
            self.recipe_slots: dict = {}

            # Sidebar
            side_scroll = ScrollView(do_scroll_x=False, size_hint_x=None, width=dp(210), bar_width=dp(4))
            self.side = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2), padding=(0, dp(2)))
            self.side.bind(minimum_height=self.side.setter("height"))
            side_scroll.add_widget(self.side)
            paint(side_scroll, theme_colour("surfaceContainerLowColor", (0.12, 0.12, 0.14, 1)), radius=10)
            self.add_widget(side_scroll)

            # Content
            right = MDBoxLayout(orientation="vertical", spacing=dp(4))
            bar = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(6))
            self.heading = MDLabel(text="", markup=True, font_style="Title", role="medium")
            bar.add_widget(self.heading)
            self.reset_button = self._button("Reset view", lambda *_: self._map and self._map.reset(), bar)
            self.hide_button = self._toggle_button("Hide done", "hide_checked", bar)
            self.logic_button = self._toggle_button("Ready only", "logic_only", bar)
            right.add_widget(bar)
            self.summary = label("")
            right.add_widget(self.summary)
            self.content = MDBoxLayout(orientation="vertical")
            self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(6))
            self.body = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6), padding=(dp(4), 0))
            self.body.bind(minimum_height=self.body.setter("height"))
            self.scroll.add_widget(self.body)
            self.content.add_widget(self.scroll)
            right.add_widget(self.content)
            self.add_widget(right)

            Clock.schedule_interval(lambda dt: self.refresh(), 1.0)
            self.refresh(force=True)

        def _button(self, text: str, callback, parent) -> MDButton:
            button = MDButton(MDButtonText(text=text), style="outlined", size_hint_x=None, width=dp(120))
            button.bind(on_release=callback)
            parent.add_widget(button)
            return button

        def _toggle_button(self, text: str, attribute: str, parent) -> MDButton:
            def caption():
                box = md_icon("checkbox-marked" if getattr(self, attribute) else "checkbox-blank-outline")
                return f"{_ICON_FONT.format(box)}  {text}"

            text_widget = MDButtonText(text=caption(), markup=True)
            button = MDButton(text_widget, style="outlined", size_hint_x=None, width=dp(140))

            def toggle(*_args):
                setattr(self, attribute, not getattr(self, attribute))
                text_widget.text = caption()
                self.show()

            button.bind(on_release=toggle)
            parent.add_widget(button)
            return button

        # -- data -----------------------------------------------------------
        def _inputs(self):
            checked = set(getattr(ctx, "checked_locations", ()) or ())
            locations = set(getattr(ctx, "missing_locations", ()) or ()) | checked
            items = [item.item for item in getattr(ctx, "items_received", ())]
            from_game = _from_game(ctx)
            visited = _visited_from_mod(from_game)
            visited |= {LOCATION_ID_TO_MOD_NAME[i] for i in checked
                        if LOCATION_ID_TO_MOD_NAME.get(i, "").startswith(LANDMARK_PREFIX)}
            slots = from_game.get("recipe_slots") if isinstance(from_game.get("recipe_slots"), dict) else {}
            return locations, checked, items, getattr(ctx, "slot_data", None) or {}, visited, slots

        def refresh(self, force: bool = False) -> None:
            locations, checked, items, slot_data, visited, slots = self._inputs()
            signature = (len(locations), len(checked), len(items), id(slot_data), len(visited), len(slots))
            if signature == self._signature and not force:
                return
            self._signature = signature
            self.state = state_for(items)
            self.slot_data, self.recipe_slots = slot_data, slots
            self._groups = build_groups(locations, checked, items, slot_data) if locations else []
            self._landmarks = landmark_map(visited, items, slot_data)
            self._build_sidebar()
            self.show()

        @staticmethod
        def _counts(checks):
            done = sum(1 for c in checks if c.status == CHECKED)
            in_logic = sum(1 for c in checks if c.status == IN_LOGIC)
            return done, in_logic, len(checks)

        def _map_counts(self):
            all_marks = [m for _, marks in self._landmarks for m in marks]
            return (sum(1 for m in all_marks if m.status == VISITED), 0, len(all_marks))

        # -- sidebar ----------------------------------------------------------
        def _build_sidebar(self):
            self.side.clear_widgets()
            self._rows = {}
            groups = dict(self._groups)

            def caption(text):
                self.side.add_widget(label(f"[size=12sp][color=9aa3ad]{text}[/color][/size]",
                                           padding=(dp(10), dp(8), 0, dp(2))))

            def row(tab, counts):
                widget = SideRow(tab, self)
                self._rows[tab] = (widget, counts)
                self.side.add_widget(widget)

            row("Overview", self._counts([c for _, cs in self._groups for c in cs]))
            row("Map", self._map_counts())
            for title, names in (("REGIONS", REGIONS), ("CRAFTING", CRAFT_GROUPS), ("OTHER", OTHER_GROUPS)):
                present = [n for n in names if n in groups]
                if not present:
                    continue
                caption(title)
                for name in present:
                    row(name, self._counts(groups[name]))
            if self.selected not in self._rows:
                self.selected = "Overview"
            self._paint_sidebar()

        def _paint_sidebar(self):
            for tab, (widget, (done, in_logic, total)) in self._rows.items():
                if tab == "Map":
                    detail = f"{done}/{total} visited"
                else:
                    detail = f"{done}/{total}" + (f"  [color={_COLOURS[IN_LOGIC]}]+{in_logic}[/color]" if in_logic else "")
                widget.update(f"[b]{escape_markup(tab)}[/b]\n[size=12sp]{detail}[/size]", done, in_logic, total,
                              tab == self.selected)

        def select(self, tab: str):
            self.selected = tab
            self._paint_sidebar()
            self.scroll.scroll_y = 1
            self.show()

        # -- content ----------------------------------------------------------
        def _use(self, widget):
            if widget.parent is not self.content:
                self.content.clear_widgets()
                self.content.add_widget(widget)

        def show(self):
            self.body.clear_widgets()
            is_map = self.selected == "Map"
            filters = self.selected != "Overview"
            self.hide_button.opacity = self.logic_button.opacity = 1 if filters else 0
            self.hide_button.disabled = self.logic_button.disabled = not filters
            self.reset_button.opacity = 1 if is_map else 0
            self.reset_button.disabled = not is_map
            self.heading.text = f"[b]{escape_markup(self.selected)}[/b]"
            if is_map:
                self._show_map()
                return
            self._use(self.scroll)
            if not self._groups:
                self.summary.text = "Connect to a room to see your checks."
                return
            if self.selected == "Overview":
                self._show_overview()
            else:
                self._show_group(dict(self._groups).get(self.selected, []))

        def _summary_text(self, checks):
            totals = Counter(check.status for check in checks)
            return (f"[color={_COLOURS[IN_LOGIC]}][b]{totals[IN_LOGIC]}[/b] ready[/color]    "
                    f"[color={_COLOURS[OUT_OF_LOGIC]}][b]{totals[OUT_OF_LOGIC]}[/b] locked[/color]    "
                    f"[color={_COLOURS[CHECKED]}][b]{totals[CHECKED]}[/b] done[/color]    "
                    f"[size=13sp][color=9aa3ad]{_ICON_FONT.format(md_icon('gesture-tap'))} click any check "
                    f"to see its recipe, where to find it and what it needs[/color][/size]")

        def _show_overview(self):
            all_checks = [c for _, cs in self._groups for c in cs]
            self.summary.text = self._summary_text(all_checks)
            grid = MDGridLayout(cols=3, size_hint_y=None, spacing=dp(8), padding=(0, dp(4)))
            grid.bind(minimum_height=grid.setter("height"),
                      width=lambda inst, width: setattr(inst, "cols", max(1, int(width // dp(230)))))
            for tab, checks in self._groups:
                done, in_logic, total = self._counts(checks)
                card = SideRow(tab, self)
                paint(card, theme_colour("surfaceContainerHighColor", (0.18, 0.18, 0.2, 1)), radius=10)
                detail = f"{done}/{total} checked" + (
                    f",  [color={_COLOURS[IN_LOGIC]}]{in_logic} in logic[/color]" if in_logic else "")
                card.update(f"[b]{escape_markup(tab)}[/b]\n[size=12sp]{detail}[/size]", done, in_logic, total, False)
                grid.add_widget(card)
            self.body.add_widget(grid)

        def _check_tiles(self, checks, strip=()):
            grid = MDGridLayout(cols=3, size_hint_y=None, spacing=dp(6))
            grid.bind(minimum_height=grid.setter("height"),
                      width=lambda inst, width: setattr(inst, "cols", max(1, int(width // dp(290)))))
            for check in checks:
                name = check.name
                for prefix in strip:
                    if name.startswith(prefix):
                        name = name[len(prefix):]
                        break
                grid.add_widget(CheckTile(check, name, self))
            for _ in range(len(checks), 3):  # keep a short section's tiles tile-sized
                grid.add_widget(Widget(size_hint_y=None, height=0))
            return grid

        def _show_group(self, checks):
            self.summary.text = self._summary_text(checks)
            by_kind: Dict[str, List[Check]] = {}
            for check in checks:
                by_kind.setdefault(check.kind, []).append(check)
            kinds = [k for k in KIND_ORDER if k in by_kind]
            for kind in kinds:
                kind_checks = by_kind[kind]
                shown = [c for c in kind_checks
                         if not (self.hide_checked and c.status == CHECKED)
                         and not (self.logic_only and c.status != IN_LOGIC)]
                self.body.add_widget(SectionHeader(kind, *self._counts(kind_checks)))
                if shown:
                    self.body.add_widget(self._check_tiles(shown, _SECTION_PREFIXES.get(kind, ())))
                elif len(kinds) == 1:
                    self.body.add_widget(label("[color=9aa3ad]Nothing to show with these filters.[/color]"))

        def _show_map(self):
            if self._map is None:
                self._map = MapView(self)
            self._use(self._map)
            marks = [m for _, ms in self._landmarks for m in ms]
            visited = sum(1 for m in marks if m.status == VISITED)
            pins = online_data.landmark_pins()
            unpinned = sorted(m.name for m in marks if m.mod_name[len(LANDMARK_PREFIX):] not in pins)
            option = (getattr(ctx, "slot_data", None) or {}).get("landmark_checks")
            dot = _ICON_FONT.format("\U000f0765")  # circle (filled)
            ring = _ICON_FONT.format(_CIRCLE)
            self.summary.text = (
                f"[color={_COLOURS[VISITED]}]{dot} {visited} visited[/color] of {len(marks)}   "
                f"[color=f2f2f2]{dot} reachable[/color]   [color=e57373]{dot} not yet[/color]   "
                f"[color=9aa3ad]{ring} position approximate   click a pin for its name; wheel to zoom, drag to pan"
                + ("" if option else "   (Landmark Checks is off -- tracking only)")
                + (f"   not on the map: {escape_markup(', '.join(unpinned))}" if unpinned else "")
                + "[/color]")
            if not online_data.map_png() or not pins:
                # Release builds leave out the wand.com map (its terms don't allow redistributing it).
                self.summary.text = (
                    f"[color={_COLOURS[VISITED]}]{visited} visited[/color] of {len(marks)}    [color=ffb74d]The yard map "
                    "isn't included in this download. Landmarks are still tracked in each region's tab; "
                    "to add the map for your own use, run connector/tools/fetch_online_data.py --map from the "
                    "project's source.[/color]")
            self._map.update(self._landmarks, self.hide_checked, self.logic_only)

    return TrackerView()
