"""Unit tests for Character, abilities, items and AbilityFactory."""

import pytest

from core.game import (
    AbilityFactory,
    AbilityKind,
    Character,
    CharacterData,
    Fireball,
    HealingLight,
    Item,
    ItemData,
    PowerStrike,
)


def make_character(name="Hero", health=100, armor=0, attack=10):
    return Character(CharacterData(name, health, health, armor, attack))


def test_take_damage_is_reduced_by_armor():
    character = make_character(armor=5)

    dealt = character.take_damage(20)

    assert dealt == 15
    assert character.health == 85


def test_take_damage_never_goes_below_zero_health():
    character = make_character(health=10)

    character.take_damage(1000)

    assert character.health == 0
    assert not character.is_alive


def test_armor_higher_than_damage_deals_nothing():
    character = make_character(armor=50)

    dealt = character.take_damage(10)

    assert dealt == 0


def test_ignore_armor_deals_full_damage():
    character = make_character(armor=50)

    dealt = character.take_damage(10, ignore_armor=True)

    assert dealt == 10


def test_defending_halves_damage():
    character = make_character()
    character.defend()

    dealt = character.take_damage(20)

    assert dealt == 10


def test_reset_defense_restores_full_damage():
    character = make_character()
    character.defend()
    character.reset_defense()

    dealt = character.take_damage(20)

    assert dealt == 20


def test_heal_is_capped_at_max_health():
    character = make_character(health=100)
    character.take_damage(10)

    healed = character.heal(50)

    assert healed == 10
    assert character.health == 100


def test_equip_applies_stat_modifiers():
    character = make_character(health=100, armor=2, attack=10)
    item = Item(ItemData("Sword", {"attack_power": 5, "armor": 1, "health": 20}))

    character.equip(item)

    assert character.attack_power == 15
    assert character.armor == 3
    assert character.max_health == 120
    assert character.health == 120
    assert item in character.equipment


def test_equip_rejects_unknown_stat():
    character = make_character()
    item = Item(ItemData("Cursed", {"luck": 1}))

    with pytest.raises(ValueError):
        character.equip(item)


def test_equip_teaches_granted_ability():
    character = make_character()
    item = Item(ItemData("Staff"), granted_ability=Fireball(10))

    character.equip(item)

    assert character.has_ability("Fireball")


def test_restore_equipment_does_not_reapply_modifiers():
    character = make_character(armor=0)
    item = Item(ItemData("Shield", {"armor": 5}))

    character.restore_equipment(item)

    assert character.armor == 0
    assert item in character.equipment


def test_get_unknown_ability_raises():
    character = make_character()

    with pytest.raises(ValueError):
        character.get_ability("Nope")


def test_fireball_ignores_armor():
    caster, target = make_character(), make_character(armor=100)

    result = Fireball(damage=25).use(caster, target)

    assert target.health == 75
    assert "25 damage" in result.message


def test_power_strike_uses_attack_plus_bonus_and_half_armor():
    caster, target = make_character(attack=10), make_character(armor=10)

    PowerStrike(bonus_damage=5).use(caster, target)

    # 10 + 5 = 15 raw, armor 10 * 0.5 = 5 -> 10 damage
    assert target.health == 90


def test_healing_light_heals_self_when_no_target():
    caster = make_character()
    caster.take_damage(30)

    HealingLight(amount=20).use(caster)

    assert caster.health == 90


@pytest.mark.parametrize("ability", [Fireball(), PowerStrike()])
def test_targeted_abilities_require_target(ability):
    with pytest.raises(ValueError):
        ability.use(make_character(), None)


@pytest.mark.parametrize(
    "kind, params, expected_type",
    [
        (AbilityKind.FIREBALL, {"damage": "30"}, Fireball),
        (AbilityKind.POWER_STRIKE, {"bonus_damage": "7"}, PowerStrike),
        (AbilityKind.HEALING_LIGHT, {"amount": "12"}, HealingLight),
    ],
)
def test_ability_factory_builds_requested_kind(kind, params, expected_type):
    ability = AbilityFactory().create(kind, **params)

    assert isinstance(ability, expected_type)


def test_ability_to_data_and_back_is_equivalent():
    original = Fireball(damage=33)

    restored = AbilityFactory().from_data(original.to_data())

    assert isinstance(restored, Fireball)
    assert restored.damage == 33
