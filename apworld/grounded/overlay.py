"""
Notification cards drawn over the game by the Grounded Client -- in the
style of the BTD6 Archipelago mod's notifications:

    | [icon] [Progression] Insect Axe
    |        from Bob (Celeste)  ·  Chest 3

A coloured bar per item class (progression / useful / filler / trap, or
hint / DeathLink / connection), the item's icon, the item, then who it's
from or for and the location. Cards slide in at the left of the game
window, stay a few seconds, fade out, and the rest move up.

Each card is its own small borderless Tk window: always on top, never
focused, and click-through, so it can't take input away from the game.
Runs on its own thread (Tk must stay on one thread); post() is safe to call
from anywhere. Shows over the game in Windowed or Borderless display mode
-- not over exclusive Fullscreen.

Kept free of Kivy so it can be tried on its own:
    python -m worlds.grounded.overlay
"""
from __future__ import annotations

import base64
import queue
import sys
import threading
import time
from typing import NamedTuple, Optional

# Item classification colours, as Archipelago's own text client uses them.
COLOURS = {
    "progression": "#af99ef", "useful": "#6d8be8", "filler": "#00c8e8", "trap": "#fa8072",
    "hint": "#ffd34d", "deathlink": "#ff5c5c", "connected": "#2ee57a", "info": "#9aa3ad",
}
CATEGORY_LABEL = {"progression": "Progression", "useful": "Useful", "filler": "Filler", "trap": "Trap",
                  "hint": "Hint", "deathlink": "DeathLink"}

CARD_W, CARD_H, GAP = 420, 78, 8
MARGIN_X, TOP_FRACTION = 24, 0.18          # from the game window's left / top
BG, SUBTEXT, TEXT = "#111827", "#9aa3ad", "#f1f3f5"
SLIDE_S, SHOW_S, FADE_S, MOVE_S = 0.22, 5.0, 0.5, 0.18
MAX_VISIBLE = 5
ALPHA = 0.94
TICK_MS = 16


class Card(NamedTuple):
    kind: str                 # key of COLOURS
    title: str                # e.g. "Insect Axe"
    subtitle: str = ""        # e.g. "from Bob (Celeste) · Chest 3"
    icon_png: Optional[bytes] = None
    tag: bool = True          # show "[Progression]" etc. before the title


def item_kind(flags: int) -> str:
    if flags & 0b100:
        return "trap"
    if flags & 0b001:
        return "progression"
    if flags & 0b010:
        return "useful"
    return "filler"


# ---------------------------------------------------------------------------
# Win32: find the game window; make a card click-through / non-activating
# ---------------------------------------------------------------------------
def _game_rect():
    """(left, top, width, height) of the Grounded window, or None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            title = ctypes.create_unicode_buffer(128)
            user32.GetWindowTextW(hwnd, title, 128)
            if cls.value == "UnrealWindow" and title.value.strip().lower().startswith("grounded"):
                found.append(hwnd)
            return True

        user32.EnumWindows(callback, 0)
        if not found:
            return None
        rect = wintypes.RECT()
        user32.GetWindowRect(found[0], ctypes.byref(rect))
        if user32.IsIconic(found[0]):
            return None
        return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        return None


_user32 = None


def _win32():
    """user32 with the argument types these calls need (on 64-bit Windows an
    untyped HWND_TOPMOST (-1) gets truncated and SetWindowPos fails)."""
    global _user32
    if _user32 is None and sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowLongW.restype = ctypes.c_long
        _user32 = user32
    return _user32


HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOACTIVATE = 0x1, 0x10


def _make_overlay_window(hwnd: int) -> None:
    """Click-through, never activated, not in the taskbar, always on top."""
    user32 = _win32()
    if not user32:
        return
    GWL_EXSTYLE = -20
    WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x80000, 0x20
    WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_TOPMOST = 0x80, 0x8000000, 0x8
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
                          | WS_EX_NOACTIVATE | WS_EX_TOPMOST)


def _move(hwnd: int, x: int, y: int) -> None:
    user32 = _win32()
    if user32:
        user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)


# ---------------------------------------------------------------------------
# The overlay
# ---------------------------------------------------------------------------
class _Slot:
    """One card window from the pool. Windows are created and shown once,
    at start-up, then reused: a free slot sits fully transparent off-screen,
    so showing a card never maps (or activates) a new window over the game."""

    def __init__(self, window, canvas, hwnd):
        self.window, self.canvas, self.hwnd = window, canvas, hwnd
        self.busy = False
        self.born = 0.0
        self.x = self.y = self.target_y = 0.0
        self.alpha = 0.0
        self.photo = None


COMPASS_W, COMPASS_H, COMPASS_TOP_FRACTION = 520, 34, 0.06


class Overlay:
    def __init__(self, logo_png: Optional[bytes] = None):
        self.queue: "queue.Queue[Card]" = queue.Queue()
        self.logo_png = logo_png
        self.enabled = True
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        # The compass line (compass.py), shown while not None. Independent of
        # `enabled`, which is only about the notification cards.
        self.compass_text: Optional[str] = None
        self._compass_shown: Optional[str] = None

    # -- any thread ----------------------------------------------------------
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="GroundedOverlay", daemon=True)
            self._thread.start()

    def post(self, card: Card) -> None:
        if self.enabled:
            self.start()
            self.queue.put(card)

    def set_compass(self, text: Optional[str]) -> None:
        if text is not None:
            self.start()
        self.compass_text = text

    def stop(self) -> None:
        self._stop.set()

    # -- overlay thread ----------------------------------------------------------
    def _run(self) -> None:
        import tkinter as tk
        import tkinter.font as tkfont

        root = tk.Tk()
        root.withdraw()
        self._tk, self._root = tk, root
        family = "Segoe UI" if "Segoe UI" in tkfont.families(root) else "Helvetica"
        self._fonts = {
            "tag": tkfont.Font(root, family=family, size=13, weight="bold"),
            "title": tkfont.Font(root, family=family, size=13),
            "sub": tkfont.Font(root, family=family, size=10),
        }
        self._slots = [self._make_slot() for _ in range(MAX_VISIBLE)]
        self._order: list = []   # busy slots, top to bottom
        self._compass = self._make_slot(COMPASS_W, COMPASS_H)
        self._tick()
        root.mainloop()

    def _make_slot(self, width: int = CARD_W, height: int = CARD_H) -> _Slot:
        tk = self._tk
        window = tk.Toplevel(self._root)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.attributes("-alpha", 0.0)
        window.geometry(f"{width}x{height}+-4000+-4000")
        canvas = tk.Canvas(window, width=width, height=height, bg=BG, highlightthickness=0, bd=0)
        canvas.pack()
        window.update_idletasks()
        hwnd = int(window.wm_frame(), 16)
        _make_overlay_window(hwnd)
        window.update()
        return _Slot(window, canvas, hwnd)

    def _photo(self, png: Optional[bytes]):
        png = png or self.logo_png
        if not png:
            return None
        try:
            return self._tk.PhotoImage(master=self._root, data=base64.b64encode(png))
        except Exception:
            return None

    def _anchor(self, rect):
        if rect:
            left, top, width, height = rect
            return left + MARGIN_X, top + int(height * TOP_FRACTION)
        return MARGIN_X, int(self._root.winfo_screenheight() * TOP_FRACTION)

    def _draw(self, slot: _Slot, card: Card) -> None:
        canvas = slot.canvas
        canvas.delete("all")
        colour = COLOURS.get(card.kind, COLOURS["info"])
        canvas.create_rectangle(0, 0, 5, CARD_H, fill=colour, width=0)
        slot.photo = self._photo(card.icon_png)
        text_x = 22
        if slot.photo:
            canvas.create_image(14 + 32, CARD_H // 2, image=slot.photo)
            text_x = 14 + 64 + 12
        title_y = CARD_H // 2 - (11 if card.subtitle else 0)
        x = text_x
        if card.tag and card.kind in CATEGORY_LABEL:
            tag = f"[{CATEGORY_LABEL[card.kind]}] "
            canvas.create_text(x, title_y, text=tag, fill=colour, font=self._fonts["tag"], anchor="w")
            x += self._fonts["tag"].measure(tag)
        title_colour = colour if not card.tag else TEXT
        canvas.create_text(x, title_y, text=_fit(card.title, self._fonts["title"], CARD_W - x - 12),
                           fill=title_colour, font=self._fonts["title"], anchor="w")
        if card.subtitle:
            canvas.create_text(text_x, CARD_H // 2 + 14,
                               text=_fit(card.subtitle, self._fonts["sub"], CARD_W - text_x - 12),
                               fill=SUBTEXT, font=self._fonts["sub"], anchor="w")

    def _release(self, slot: _Slot) -> None:
        slot.busy = False
        slot.photo = None
        slot.canvas.delete("all")
        slot.window.attributes("-alpha", 0.0)
        _move(slot.hwnd, -4000, -4000)

    def _tick_compass(self, rect) -> None:
        text = self.compass_text
        slot = self._compass
        if text != self._compass_shown:
            self._compass_shown = text
            slot.canvas.delete("all")
            if text:
                slot.canvas.create_rectangle(0, 0, 5, COMPASS_H, fill=COLOURS["hint"], width=0)
                slot.canvas.create_text(COMPASS_W // 2, COMPASS_H // 2,
                                        text=_fit("Nearest check: " + text, self._fonts["title"], COMPASS_W - 24),
                                        fill=TEXT, font=self._fonts["title"])
        if not text:
            slot.window.attributes("-alpha", 0.0)
            _move(slot.hwnd, -4000, -4000)
            return
        if rect:
            left, top, width, height = rect
            x, y = left + (width - COMPASS_W) // 2, top + int(height * COMPASS_TOP_FRACTION)
        else:
            x, y = (self._root.winfo_screenwidth() - COMPASS_W) // 2, int(
                self._root.winfo_screenheight() * COMPASS_TOP_FRACTION)
        slot.window.attributes("-alpha", ALPHA)
        _move(slot.hwnd, x, y)

    def _tick(self) -> None:
        if self._stop.is_set():
            self._root.destroy()
            return
        rect = _game_rect()
        try:
            self._tick_compass(rect)
        except Exception:
            pass
        now = time.monotonic()
        anchor_x, anchor_y = self._anchor(rect)
        # New cards, while a slot is free.
        free = [slot for slot in self._slots if not slot.busy]
        while free:
            try:
                card = self.queue.get_nowait()
            except queue.Empty:
                break
            slot = free.pop(0)
            try:
                self._draw(slot, card)
            except Exception:
                continue
            slot.busy, slot.born = True, now
            slot.y = slot.target_y = anchor_y + len(self._order) * (CARD_H + GAP)
            slot.x = anchor_x - CARD_W
            self._order.append(slot)
        # Animate: slide in, hold, fade out; the rest move up.
        still = []
        for slot in self._order:
            age = now - slot.born
            if age < SLIDE_S:
                ease = 1 - (1 - age / SLIDE_S) ** 3
                slot.x = anchor_x - CARD_W * (1 - ease)
                slot.alpha = ALPHA * ease
            elif age < SLIDE_S + SHOW_S:
                slot.x, slot.alpha = anchor_x, ALPHA
            elif age < SLIDE_S + SHOW_S + FADE_S:
                slot.x = anchor_x
                slot.alpha = ALPHA * (1 - (age - SLIDE_S - SHOW_S) / FADE_S)
            else:
                self._release(slot)
                continue
            still.append(slot)
        self._order = still
        for index, slot in enumerate(self._order):
            slot.target_y = anchor_y + index * (CARD_H + GAP)
            slot.y += (slot.target_y - slot.y) * min(1.0, (TICK_MS / 1000) / MOVE_S * 3)
            try:
                slot.window.attributes("-alpha", max(0.0, slot.alpha))
                _move(slot.hwnd, int(slot.x), int(slot.y))
            except Exception:
                pass
        self._root.after(TICK_MS, self._tick)


def _fit(text: str, font, width: int) -> str:
    if font.measure(text) <= width:
        return text
    while text and font.measure(text + "…") > width:
        text = text[:-1]
    return text + "…"


if __name__ == "__main__":
    # Try the look without a game or server.
    overlay = Overlay()
    overlay.post(Card("progression", "Insect Axe", "from Matthew (Celeste)  ·  Crystal Heart 3"))
    overlay.post(Card("filler", "Plant Fiber Bundle", "from your world  ·  Item: Sprig"))
    overlay.post(Card("useful", "Moon Boots", "to Alice (A Link to the Past)  ·  Craft: Black Ant Sword"))
    overlay.post(Card("connected", "You have connected.", tag=False))
    time.sleep(8)
