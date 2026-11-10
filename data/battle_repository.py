"""Persistence for the text game: an unfinished battle (to continue it
later) and the history of finished battles (results table)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from core.game import Battle, BattleResult, EnemyAI, Game

from . import game_serializer


class BattleRepository:
    """Saves / loads the full state of a battle in progress."""

    def save(self, path: str, battle: Battle) -> None:
        heroes = [(f"h{i}", c) for i, c in enumerate(battle.heroes, start=1)]
        enemies = [(f"e{i}", c) for i, c in enumerate(battle.enemies, start=1)]
        payload = {
            "round": battle.round,
            "acted": sorted(battle.acted_indexes),
            "damage_dealt": dict(battle.statistics.damage_dealt),
            "damage_taken": dict(battle.statistics.damage_taken),
            "catalog": game_serializer.catalog_to_dict(heroes + enemies, [], []),
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: str, game: Game, ai: EnemyAI | None = None) -> Battle:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        characters, _, _ = game_serializer.catalog_from_dict(payload["catalog"])
        heroes = [c for key, c in characters if key.startswith("h")]
        enemies = [c for key, c in characters if key.startswith("e")]
        battle = Battle(game, heroes, enemies, ai, clone=False)
        battle.restore_progress(payload.get("round", 1), set(payload.get("acted", [])),
                                payload.get("damage_dealt"), payload.get("damage_taken"))
        return battle


class ResultsRepository:
    """Append-only JSON list of finished battles."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)

    @property
    def path(self) -> str:
        return str(self._path)

    def all(self) -> list[BattleResult]:
        if not self._path.is_file():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [BattleResult(**entry) for entry in raw]

    def append(self, result: BattleResult) -> None:
        results = self.all() + [result]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8"
        )
