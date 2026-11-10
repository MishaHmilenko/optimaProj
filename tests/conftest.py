"""Shared pytest fixtures.

Fixtures build the test context (fake HTTP transport, API client,
service with a seeded random generator) once per test, so individual
tests only contain their own Arrange/Act/Assert steps.
"""

import random
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SAMPLES_DIR = PROJECT_ROOT / "samples" / "genshin"


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR


@pytest.fixture
def file_http_client(samples_dir):
    from infra import FileHttpClient

    return FileHttpClient(str(samples_dir))


@pytest.fixture
def genshin_api(file_http_client):
    from infra import GenshinApiClient

    return GenshinApiClient(file_http_client)


@pytest.fixture
def stat_generator():
    from services import StatGenerator

    return StatGenerator(random.Random(42))


@pytest.fixture
def genshin_service(genshin_api, stat_generator):
    from services import GenshinMapper, GenshinService

    return GenshinService(genshin_api, GenshinMapper(stat_generator))


# -- CLI ---------------------------------------------------------------------------


class CliHarness:
    """A characters-mode CLI wired to an in-memory console. run() returns
    only the output produced by that one command."""

    def __init__(self, cli, ctx, console) -> None:
        self.cli = cli
        self.ctx = ctx
        self.console = console

    @property
    def catalog(self):
        return self.ctx.catalog

    def run(self, line: str, *answers: str) -> str:
        self.console.feed(*answers)
        start = len(self.console.lines)
        self.cli.exec_command(line)
        return "\n".join(self.console.lines[start:])


@pytest.fixture
def chars(genshin_service, tmp_path):
    from cli import build_characters_cli
    from cli.framework import BufferConsole

    console = BufferConsole()
    cli, ctx = build_characters_cli(console, service=genshin_service, save_dir=str(tmp_path / "saves"),
                                    rng=random.Random(7))
    return CliHarness(cli, ctx, console)
