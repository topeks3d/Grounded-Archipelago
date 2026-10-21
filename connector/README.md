# Grounded Archipelago Connector

The network half of the integration -- see `../ARCHITECTURE.md` for why this
exists as a separate process instead of living entirely in the UE4SS mod.

The actual client code lives in `../apworld/grounded/client.py`, inside the
apworld package itself, and gets registered as an Archipelago Launcher
**Component** ("Grounded Client") in `../apworld/grounded/__init__.py`. This
matters more than it sounds like it should: it means the client runs using
whatever Archipelago environment is already loaded -- compiled Windows
installer or source checkout -- instead of needing its own separate,
importable copy of `CommonClient.py` on disk, which the compiled installer
generally doesn't provide (see "Two ways to install Archipelago" below).

## Installing the world

**Compiled Windows installer** (the default -- e.g. Archipelago lives at
`C:\ProgramData\Archipelago`): zip up `../apworld/grounded` as
`grounded.apworld` and drop it in `C:\ProgramData\Archipelago\custom_worlds\`.
(A `.apworld` is just that folder zipped with a `.apworld` extension instead
of `.zip` -- rename after zipping, or use PowerShell's
`Compress-Archive -Path apworld\grounded\* -DestinationPath grounded.apworld`.)

**Source checkout** (you cloned/downloaded
https://github.com/ArchipelagoMW/Archipelago yourself): copy
`../apworld/grounded` into that checkout's `worlds/` folder, so it ends up at
`<Archipelago>/worlds/grounded/`.

Either way, both the server (for generating/hosting a seed) and the client
need the world installed -- and once it is, "Grounded Client" will show up
as a button in the Archipelago Launcher GUI too, not just via the CLI
commands below.

If `apworld/grounded/items.py` or `locations.py` ever change, regenerate
`apworld/grounded/grounded_data.py` (the plain name->id table the client
reads, kept separate so the client doesn't need to import `BaseClasses`/
`Options`/etc. just to know two dictionaries):
```
python tools/generate_grounded_data.py /path/to/an/Archipelago/source/checkout
```
This always needs a source checkout to run (it imports the apworld, which
imports `BaseClasses`), even if you're distributing the result to people
using the compiled installer.

## Running the client

**The easy way (standard Steam install, no terminal needed):** open the
Archipelago Launcher (the normal GUI app, `ArchipelagoLauncher.exe` or
`python Launcher.py`) and click the "Grounded Client" button that appears
there once the world is installed. A client window opens with a text box
for the server address -- type `archipelago.gg:38281` (or whatever your
room's address is) and connect, the same as any other Archipelago client.
`--ipc-dir` now auto-detects a standard Steam install (checked via the
Windows registry, then a few common library locations) -- you only need
to type anything into a terminal at all if that detection fails (a
non-standard install location, or the mod not actually installed there
yet), and even then it's a one-time `--ipc-dir` override, not the whole
command below.

**Manual / non-standard install**, if auto-detection didn't find your
game:
```
ArchipelagoLauncher.exe "Grounded Client" -- --ipc-dir "<the IPC folder the mod printed on load>" --connect <server address:port> --name <your slot name> --nogui
```

**Source checkout**, either the same Launcher approach...
```
python Launcher.py "Grounded Client" -- --ipc-dir "..." --connect ... --name ... --nogui
```
...or the standalone script in this folder, which just saves you a couple of
characters of typing and works identically:
```
python grounded_connector.py \
    --archipelago-dir /path/to/Archipelago \
    --ipc-dir "/path/to/Grounded/.../ue4ss/Mods/GroundedArchipelago/ipc" \
    --connect archipelago.gg:38281 \
    --name YourSlotName \
    --nogui
```

Either way:
* `--ipc-dir`, whether auto-detected or passed by hand, must be the exact
  same folder the Lua mod resolves in `Scripts/config.lua`. The mod
  prints the folder it's using on load -- check the UE4SS console/log if
  auto-detection picked the wrong one or you're passing it manually.
* Drop `--nogui` if you want the graphical client window instead of a plain
  terminal client (needs Archipelago's `kivy`/`kivymd` dependencies, which
  the compiled installer already includes).
* Once connected, `!help` lists server-side commands and `/help` lists local
  ones. `/ipc_status` shows the current IPC paths and how many locations
  have been sent to the server so far -- handy for confirming the mod and
  client are pointed at the same folder.

## Two ways to install Archipelago (and why it matters here)

Archipelago ships two different ways, and they matter for anything (like
this) that isn't a pre-built client .exe:

* **The compiled Windows installer** (what most players use) bundles a
  frozen Python runtime. Its `lib\` folder is full of version-specific
  compiled `.pyd` files and a `library.zip` containing the actual Python
  modules as bytecode -- there's no loose, generically-importable
  `CommonClient.py` sitting on disk to point a separate `python.exe` at.
  This is exactly what the Launcher Component approach above sidesteps: the
  Component's code runs *inside* that already-loaded environment (via
  `worlds/LauncherComponents.py`'s `launch`/`launch_subprocess`), so it
  never needs to import anything from outside that process.
* **A source checkout** has `CommonClient.py`, `Utils.py`, etc. as plain
  files at the repo root, importable by any matching Python install. This is
  what `grounded_connector.py`'s `--archipelago-dir` bootstrapping is for,
  and what this connector was actually tested against end-to-end (see
  below).

## What this was actually tested against

This has been run against a real, locally-hosted Archipelago server
(`MultiServer.py`) with seeds generated from this world, through **both**
invocation paths above (the standalone script with `--archipelago-dir`, and
`Launcher.py "Grounded Client"`): connecting, receiving `slot_data`,
receiving previously-earned items on reconnect, translating a simulated
location-check file into a `LocationChecks` packet, receiving the resulting
item back through `ReceivedItems` and writing it to `to_game.json`, and
sending a goal-complete `StatusUpdate` -- all round-tripped successfully.
What is *not* tested (and can't be, outside a Windows machine with the
actual game and the actual compiled installer) is the other end of that
file exchange -- the UE4SS Lua mod actually being the one writing
`from_game.json` from real gameplay, and the Component actually launching
correctly from a real frozen `ArchipelagoLauncher.exe` rather than the
source-checkout `Launcher.py` I tested with.
