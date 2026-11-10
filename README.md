# OOP course project — characters catalog & text game (practical 13: CLI)

Design document: **[DESIGN.md](DESIGN.md)** (architecture + detailed description of the console interface).
Earlier practicals: [BEHAVIORAL_PATTERNS.md](BEHAVIORAL_PATTERNS.md) (11), [PATTERNS.md](PATTERNS.md) (9),
[FILEMAN.md](FILEMAN.md) (12, `python3 files.py`).

## Run

    pip install -r requirements.txt            # only needed for the tests
    python3 main.py                            # choose a mode in a dialog
    python3 main.py --chars                    # live API: https://genshin.jmp.blue
    python3 main.py --chars --offline          # bundled samples in samples/genshin (no network)
    python3 main.py --chars --offline db chars # run one command and exit
    python3 main.py --text                     # structured text documents

Other options: `--load PATH` (load a catalog at start), `--saves DIR` (where saves/results go,
default `saves/`), `--seed N` (reproducible stats and enemy moves).

## Commands (characters mode) — `help` / `help <command>` inside the program

| Category | Commands |
|---|---|
| Information | `ls [char\|item\|ability]`, `show <id>`, `sheet <id> [--toc] [--format …]`, `stats` |
| Actions | `create <char\|item\|ability>` (dialog), `add <char> <item\|ability>`, `act …`, `undo`, `rm <id>` |
| Remote database | `db refresh`, `db chars`, `db weapons`, `db show <char\|weapon> <slug>`, `db create <slug>`, `db equip <char> <weapon>` |
| Storage | `save [path]`, `load [path]` |
| Text game | `game roster`, `game start [--team c1,c2] [--enemies c3\|random]`, `game resume`, `game results` |
| In battle (`battle>`) | `status`, `attack [#]`, `skill <#\|name> [#]`, `heal [#]`, `defend`, `flee`, `save`, `back` |
| Everywhere | `help`, `back`, `exit` |

Recorded sessions (input and output) are in `usage/`:

    python3 main.py --chars --offline --seed 13 < usage/catalog_session.txt
    python3 main.py --chars --offline --seed 13 < usage/game_session.txt

## Tests

    python3 -m pytest -q

## Layers

    core/      game (characters, battle rules) + text systems
    infra/     HTTP clients, Genshin API client + DTOs, IRenderer/IRenderable, IDisplayer
    services/  GenshinService (cached facade), mapper DTO -> core, character sheet
    data/      JSON persistence: catalog, battle state, battle results
    cli/       framework/ (CLI facade, Args, Command, strategies, CLIGraphic, ConsoleRenderer),
               strategies/ (command categories), app.py (composition root)
    fileman/   full-screen file manager (practical 12)
    tests/     pytest suite

## API note

API: https://genshin.jmp.blue (https://github.com/genshindev/api). It has no base stats,
so HP / armor / attack are rolled from a range depending on rarity (services/stat_generator.py).
Weapon base attack becomes an attack bonus (baseAttack // 5). Talent damage is
attack × 1.0 / 1.5 / 2.5 for normal attack / skill / burst. The public API is sometimes
down (HTTP 521) — use `--offline` then.
