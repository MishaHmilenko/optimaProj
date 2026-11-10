"""Composition root: the only place that decides which implementations
are used (real API or offline samples, console, file locations) and
which strategies the CLI facade is parametrised with.

    python3 main.py                         ask for a mode in a dialog
    python3 main.py --chars [--offline]     characters catalog + game
    python3 main.py --text                  structured text editor
    python3 main.py --chars --offline ls    run one command and exit
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from core.game import Game
from data import BattleRepository, Repository, ResultsRepository
from infra import FileHttpClient, GenshinApiClient, IHttpClient, UrllibHttpClient
from services import GenshinMapper, GenshinService, StatGenerator

from .framework import CLI, CommandError, IConsole
from .state import Catalog, CharactersContext
from .strategies import (
    CatalogActionStrategy,
    CatalogInfoStrategy,
    DatabaseStrategy,
    GameStrategy,
    StorageStrategy,
)
from .text_cli import TextDocumentStrategy, TextNavigator

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples" / "genshin"
MODES = {"chars": "characters catalog and text game", "text": "structured text document"}


def build_genshin_service(offline: bool, rng: random.Random | None = None) -> GenshinService:
    http: IHttpClient = FileHttpClient(str(SAMPLES_DIR)) if offline else UrllibHttpClient()
    return GenshinService(GenshinApiClient(http), GenshinMapper(StatGenerator(rng or random.Random())))


def build_characters_cli(console: IConsole | None = None, *, offline: bool = False,
                         service: GenshinService | None = None, save_dir: str = "saves",
                         rng: random.Random | None = None) -> tuple[CLI, CharactersContext]:
    cli = CLI(console)
    ctx = CharactersContext(
        catalog=Catalog(),
        game=Game(cli.as_displayer()),
        repository=Repository(),
        service=service or build_genshin_service(offline, rng),
        battles=BattleRepository(),
        results=ResultsRepository(str(Path(save_dir) / "results.json")),
        save_path=str(Path(save_dir) / "catalog.json"),
        battle_path=str(Path(save_dir) / "battle.json"),
    )
    cli.use_strategy(CatalogInfoStrategy(ctx))
    cli.use_strategy(CatalogActionStrategy(ctx))
    cli.use_strategy(DatabaseStrategy(ctx))
    cli.use_strategy(StorageStrategy(ctx))
    cli.use_strategy(GameStrategy(ctx, rng))
    return cli, ctx


def build_text_cli(console: IConsole | None = None) -> tuple[CLI, TextNavigator]:
    cli = CLI(console)
    nav = TextNavigator()
    cli.use_strategy(TextDocumentStrategy(nav, Repository()))
    return cli, nav


def _offer_save(cli: CLI, ctx: CharactersContext) -> None:
    if not ctx.catalog.dirty or not cli.console.interactive:
        return
    try:
        if cli.dialog.confirm(f"Save changes to {ctx.save_path} before exit?", default=True):
            cli.exec_command("save")
    except CommandError:
        pass


def parse_startup(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="main.py", description="Characters catalog / text game CLI")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--chars", "--characters", "-c", dest="mode", action="store_const", const="chars")
    group.add_argument("--text", "-t", dest="mode", action="store_const", const="text")
    parser.add_argument("--offline", action="store_true", help="use bundled samples instead of the API")
    parser.add_argument("--load", metavar="PATH", help="load a saved catalog at start")
    parser.add_argument("--saves", default="saves", metavar="DIR", help="folder for saves and results")
    parser.add_argument("--seed", type=int, help="random seed (reproducible stats and enemy moves)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="run one command and exit")
    return parser.parse_args(argv)


def choose_mode(cli: CLI) -> str:
    cli.info("No mode selected at startup (use --chars or --text).")
    labels = [f"{key} — {text}" for key, text in MODES.items()]
    return cli.dialog.choose("Mode", labels).split(" ")[0]


def main(argv: list[str] | None = None, console: IConsole | None = None) -> int:
    import sys
    options = parse_startup(sys.argv[1:] if argv is None else argv)
    mode = options.mode
    if mode is None:
        try:
            mode = choose_mode(CLI(console))
        except CommandError as exc:
            print(exc)
            return 1

    if mode == "text":
        cli, _ = build_text_cli(console)
        if options.command:
            return 0 if cli.exec_command(" ".join(options.command)) else 1
        cli.run("=== Text document ===")
        return 0

    rng = random.Random(options.seed) if options.seed is not None else None
    cli, ctx = build_characters_cli(console, offline=options.offline, save_dir=options.saves, rng=rng)
    if options.load:
        cli.exec_command(f'load "{options.load}"')
    if options.command:
        return 0 if cli.exec_command(" ".join(_quote(t) for t in options.command)) else 1
    source = "offline samples" if options.offline else "https://genshin.jmp.blue"
    cli.run(cli.style(f"=== Characters catalog & text game (database: {source}) ===", "bold"))
    _offer_save(cli, ctx)
    return 0


def _quote(token: str) -> str:
    return f'"{token}"' if " " in token else token
