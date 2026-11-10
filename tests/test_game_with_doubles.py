"""Game is tested as a black box through its IDisplayer dependency:
we never look inside Game, only at what it sends to the displayer.

Uses both the hand-written doubles (tests/doubles.py) and pytest-mock
for the auto-generated variant."""

import pytest

from core.game import Character, CharacterData, Fireball, Game, Item, ItemData
from infra import IDisplayer, Message

from .doubles import FakeDisplayer, MockDisplayer, StubDisplayer


def make_character(name, health=100, armor=0, attack=10):
    return Character(CharacterData(name, health, health, armor, attack))


def test_game_works_with_fake_displayer():
    game = Game(FakeDisplayer())
    attacker, target = make_character("A"), make_character("B")

    game.basic_attack(attacker, target)

    assert target.health == 90


def test_basic_attack_displays_exactly_one_message():
    displayer = MockDisplayer()
    game = Game(displayer)

    game.basic_attack(make_character("A"), make_character("B"))

    assert displayer.call_count == 1
    assert "A attacks B for 10 damage" in displayer.messages[0]


def test_use_ability_displays_ability_result():
    displayer = MockDisplayer()
    game = Game(displayer)
    caster, target = make_character("Mage"), make_character("Orc")
    caster.learn_ability(Fireball(damage=20))

    game.use_ability(caster, "Fireball", target)

    assert displayer.messages == ["Mage hurls a Fireball at Orc for 20 damage!"]


def test_unknown_ability_displays_nothing():
    displayer = MockDisplayer()
    game = Game(displayer)

    with pytest.raises(ValueError):
        game.use_ability(make_character("A"), "Nope", make_character("B"))

    assert displayer.call_count == 0


def test_report_status_displays_one_line_per_character():
    displayer = MockDisplayer()
    game = Game(displayer)
    game.add_character(make_character("A"))
    game.add_character(make_character("B"))

    game.report_status()

    assert displayer.call_count == 2


def test_displayer_failure_propagates_but_state_is_already_changed():
    game = Game(StubDisplayer(fail_on="attacks"))
    target = make_character("B")

    with pytest.raises(RuntimeError):
        game.basic_attack(make_character("A"), target)

    assert target.health == 90


def test_equip_item_with_pytest_mock(mocker):
    displayer = mocker.Mock(spec=IDisplayer)
    game = Game(displayer)
    character = make_character("Knight")

    game.equip_item(character, Item(ItemData("Shield", {"armor": 3})))

    displayer.display.assert_called_once_with(Message("Knight equips Shield."))
    assert character.armor == 3


def test_heal_with_pytest_mock_reports_actual_amount(mocker):
    displayer = mocker.Mock(spec=IDisplayer)
    game = Game(displayer)
    healer = make_character("Cleric")
    healer.take_damage(5)

    game.heal(healer, amount=50)

    displayer.display.assert_called_once_with(Message("Cleric heals Cleric for 5 HP."))
