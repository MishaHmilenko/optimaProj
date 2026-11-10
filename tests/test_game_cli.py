"""The text game: Battle rules (core), battle persistence (data) and the
game / battle-mode commands (cli)."""

import random

import pytest

from core.game import Battle, Character, CharacterData, EnemyAI, Fireball, Game, Outcome
from data import BattleRepository, ResultsRepository

from .doubles import FakeDisplayer


def make(name, hp=100, armor=0, attack=10):
    return Character(CharacterData(name, hp, hp, armor, attack))


@pytest.fixture
def game():
    return Game(FakeDisplayer())


# -- core ----------------------------------------------------------------------------


def test_battle_fights_clones_and_keeps_catalog_intact(game):
    hero, enemy = make("Hero", attack=30), make("Orc", hp=40)
    battle = Battle(game, [hero], [enemy], EnemyAI(random.Random(1)))

    battle.attack(battle.enemies[0])
    battle.attack(battle.enemies[0])

    assert battle.outcome is Outcome.VICTORY
    assert enemy.health == 40 and hero.health == 100


def test_enemies_act_after_every_hero_has_acted(game):
    battle = Battle(game, [make("A"), make("B")], [make("Orc", attack=12)], EnemyAI(random.Random(1)))

    battle.defend()
    assert battle.round == 1 and battle.current_hero.name == "B"
    battle.attack(battle.enemies[0])

    assert battle.round == 2
    assert battle.current_hero.name == "A"
    # equal HP -> the first hero is targeted; A was defending, so damage is halved
    assert battle.heroes[0].health == 94
    assert not battle.heroes[0].is_defending  # stance resets for the new round


def test_defeat_when_all_heroes_fall(game):
    battle = Battle(game, [make("Weak", hp=10)], [make("Boss", hp=500, attack=50)])

    battle.attack(battle.enemies[0])

    assert battle.outcome is Outcome.DEFEAT
    with pytest.raises(ValueError):
        battle.attack(battle.enemies[0])


def test_heal_needs_missing_health(game):
    battle = Battle(game, [make("Cleric", attack=20)], [make("Orc", attack=30)])

    with pytest.raises(ValueError, match="full health"):
        battle.heal(None)
    battle.attack(battle.enemies[0])  # Orc hits back: 100 -> 70
    battle.heal(None)                 # +10 (attack // 2) -> 80, Orc hits again -> 50

    assert battle.heroes[0].health == 50
    assert battle.round == 3


def test_ability_and_result(game):
    mage = make("Mage")
    mage.learn_ability(Fireball(damage=50))
    battle = Battle(game, [mage], [make("Orc", hp=50)])

    battle.use_ability("fireball", battle.enemies[0])
    result = battle.result()

    assert result.outcome == "victory"
    assert result.damage_dealt == 50 and result.survivors == ["Mage"]


def test_flee(game):
    battle = Battle(game, [make("A")], [make("B")])
    battle.flee()

    assert battle.is_over and battle.result().outcome == "fled"


def test_battle_save_and_load_round_trip(game, tmp_path):
    battle = Battle(game, [make("A", attack=25), make("B")], [make("Orc", hp=200, attack=7)])
    battle.attack(battle.enemies[0])
    path = str(tmp_path / "battle.json")

    BattleRepository().save(path, battle)
    loaded = BattleRepository().load(path, Game(FakeDisplayer()))

    assert loaded.round == 1 and loaded.current_hero.name == "B"
    assert loaded.enemies[0].health == 175
    assert loaded.result().damage_dealt == 25


def test_results_repository_appends(tmp_path, game):
    repo = ResultsRepository(str(tmp_path / "r" / "results.json"))
    battle = Battle(game, [make("A")], [make("B")])
    battle.flee()

    repo.append(battle.result())
    repo.append(battle.result())

    assert [r.outcome for r in repo.all()] == ["fled", "fled"]


# -- cli -------------------------------------------------------------------------------


def hero_and_orc(chars):
    chars.run("create char", "Hero", "200", "0", "60", "", "", "")
    chars.run("create char", "Orc", "100", "0", "5", "", "", "")


def test_game_start_without_characters(chars):
    assert "No characters to play with" in chars.run("game start")


def test_game_roster(chars):
    hero_and_orc(chars)

    out = chars.run("game roster")

    assert "Hero" in out and "Orc" in out


def test_full_game_until_victory(chars):
    hero_and_orc(chars)

    out = chars.run("game start --team c1 --enemies c2")
    assert chars.cli.mode.name == "battle"
    assert chars.cli.find_command("ls") is None  # catalog commands hidden in battle
    assert "Round 1" in out

    chars.run("attack 1")
    out = chars.run("attack")

    assert "VICTORY" in out
    assert chars.cli.mode.name == "main"
    assert chars.catalog.find_character("Orc").health == 100  # catalog untouched
    results = chars.run("game results")
    assert "victory" in results and "1 battle(s), 1 victory" in results


def test_game_start_through_dialog(chars):
    hero_and_orc(chars)

    chars.run("game start", "c1", "c2")

    assert chars.cli.mode.name == "battle"


def test_random_enemies_come_from_database(chars):
    hero_and_orc(chars)

    out = chars.run("game start --team c1 --enemies random --count 2")

    assert "Enemies from the database" in out
    assert "battle" == chars.cli.mode.name


def test_same_character_cannot_be_on_both_sides(chars):
    hero_and_orc(chars)

    assert "both sides" in chars.run("game start --team c1 --enemies c1")


def test_invalid_target_does_not_use_the_turn(chars):
    hero_and_orc(chars)
    chars.run("game start --team c1 --enemies c2")

    out = chars.run("attack 9")

    assert "No enemy '9'" in out
    assert "Round 1" in chars.run("status")


def test_skill_by_number(chars):
    chars.run("db create albedo")
    chars.run("create char", "Dummy", "1000", "0", "1", "", "", "")
    chars.run("game start --team c1 --enemies c2")

    out = chars.run("skill 2 1")

    assert "Abiogenesis" in out


def test_battle_save_and_resume(chars):
    chars.run("create char", "Hero", "200", "0", "20", "", "", "")
    chars.run("create char", "Orc", "100", "0", "5", "", "", "")
    chars.run("game start --team c1 --enemies c2")
    chars.run("attack")

    assert "Battle saved" in chars.run("save")
    chars.run("back")
    assert chars.cli.mode.name == "main"

    out = chars.run("game resume")
    assert chars.cli.mode.name == "battle"
    assert "80/100" in out


def test_flee_asks_for_confirmation(chars):
    hero_and_orc(chars)
    chars.run("game start --team c1 --enemies c2")

    chars.run("flee", "n")
    assert chars.cli.mode.name == "battle"
    out = chars.run("flee", "y")

    assert "FLED" in out and chars.cli.mode.name == "main"
