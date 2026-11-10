"""Services: stat generation, DTO -> core mapping, the facade service
and the structured-text character sheet (written test-first)."""

import random

import pytest

from core.game import (
    AbilityFactory,
    Character,
    CharacterData,
    Item,
    ItemData,
    TalentAbility,
)
from core.text import Heading
from infra import CharacterDto, RemoteServiceError, TalentDto, WeaponDto
from services import CharacterSheetBuilder, GenshinMapper, StatGenerator

from .doubles import FakeHttpClient


# -- StatGenerator -------------------------------------------------------------


@pytest.mark.parametrize("rarity", [3, 4, 5])
def test_generated_stats_stay_inside_rarity_ranges(rarity):
    low, high = StatGenerator.RANGES[rarity]

    for seed in range(200):
        stats = StatGenerator(random.Random(seed)).generate(rarity)
        assert low.health <= stats.health <= high.health
        assert low.armor <= stats.armor <= high.armor
        assert low.attack_power <= stats.attack_power <= high.attack_power


def test_same_seed_gives_same_stats():
    first = StatGenerator(random.Random(7)).generate(5)
    second = StatGenerator(random.Random(7)).generate(5)

    assert first == second


def test_unknown_rarity_falls_back_to_lowest_range():
    stats = StatGenerator(random.Random(1)).generate(1)
    low, high = StatGenerator.RANGES[3]

    assert low.health <= stats.health <= high.health


def test_five_star_is_stronger_on_average_than_four_star():
    rng = random.Random(0)
    generator = StatGenerator(rng)

    five = [generator.generate(5).attack_power for _ in range(100)]
    four = [generator.generate(4).attack_power for _ in range(100)]

    assert sum(five) > sum(four)


# -- TalentAbility (new core ability built for API talents) -------------------


def make_character(attack=10, armor=0, weapon_type=""):
    return Character(CharacterData("C", 100, 100, armor, attack, weapon_type=weapon_type))


@pytest.mark.parametrize(
    "talent_type, expected_damage",
    [("NORMAL_ATTACK", 10), ("ELEMENTAL_SKILL", 15), ("ELEMENTAL_BURST", 25)],
)
def test_talent_damage_scales_with_type(talent_type, expected_damage):
    talent = TalentAbility.for_type("T", "desc", talent_type)
    caster, target = make_character(attack=10), make_character()

    talent.use(caster, target)

    assert target.health == 100 - expected_damage


def test_talent_requires_target():
    with pytest.raises(ValueError):
        TalentAbility.for_type("T", "d", "ELEMENTAL_SKILL").use(make_character(), None)


def test_talent_round_trips_through_ability_factory():
    original = TalentAbility.for_type("Pyronado", "Spins fire", "ELEMENTAL_BURST")

    restored = AbilityFactory().from_data(original.to_data())

    assert isinstance(restored, TalentAbility)
    assert restored.name == "Pyronado"
    assert restored.description == "Spins fire"
    assert restored.multiplier == original.multiplier


# -- weapon type restriction (Character.can_equip) ------------------------------------


def test_character_cannot_equip_wrong_weapon_type():
    swordsman = make_character(weapon_type="Sword")
    claymore = Item(ItemData("Big", {"attack_power": 5}, item_type="Claymore"))

    assert not swordsman.can_equip(claymore)
    with pytest.raises(ValueError):
        swordsman.equip(claymore)
    assert swordsman.attack_power == 10


def test_untyped_items_fit_anyone():
    swordsman = make_character(weapon_type="Sword")

    assert swordsman.can_equip(Item(ItemData("Ring", {"armor": 1})))


# -- GenshinMapper ------------------------------------------------------------------


@pytest.fixture
def character_dto():
    return CharacterDto(
        slug="xiangling",
        name="Xiangling",
        title="Exquisite Delicacy",
        vision="Pyro",
        weapon_type="Polearm",
        rarity=4,
        nation="Liyue",
        description="A chef.",
        talents=(
            TalentDto("Dough-Fu", "Normal Attack", "Five thrusts.", "NORMAL_ATTACK"),
            TalentDto("Pyronado", "Elemental Burst", "Fire spin.", "ELEMENTAL_BURST"),
        ),
    )


def test_mapper_copies_identity_fields(character_dto, stat_generator):
    character = GenshinMapper(stat_generator).to_character(character_dto)

    assert character.name == "Xiangling"
    assert character.data.vision == "Pyro"
    assert character.data.weapon_type == "Polearm"
    assert character.data.rarity == 4
    assert character.data.description == "A chef."


def test_mapper_starts_character_at_full_health(character_dto, stat_generator):
    character = GenshinMapper(stat_generator).to_character(character_dto)

    assert character.health == character.max_health


def test_mapper_turns_talents_into_abilities(character_dto, stat_generator):
    character = GenshinMapper(stat_generator).to_character(character_dto)

    assert character.abilities == ("Dough-Fu", "Pyronado")
    assert character.get_ability("Pyronado").talent_type == "ELEMENTAL_BURST"


def test_mapper_converts_weapon_to_typed_item(stat_generator):
    dto = WeaponDto("the-catch", "The Catch", "Polearm", 4, 42, "Energy Recharge", "Shanty", "Burst DMG up.")

    item = GenshinMapper(stat_generator).to_item(dto)

    assert item.name == "The Catch"
    assert item.data.item_type == "Polearm"
    assert item.data.rarity == 4
    assert item.stat_modifiers == {"attack_power": 8}
    assert "Shanty" in item.data.description


def test_weapon_bonus_is_at_least_one(stat_generator):
    dto = WeaponDto("w", "Twig", "Sword", 1, 2, "", "", "")

    assert GenshinMapper(stat_generator).to_item(dto).stat_modifiers == {"attack_power": 1}


# -- GenshinService (facade over api + mapper, with caching) ----------------------------


def test_service_creates_character_from_api(genshin_service):
    albedo = genshin_service.create_character("albedo")

    assert albedo.name == "Albedo"
    assert len(albedo.abilities) == 3


def test_service_caches_dtos_between_calls(stat_generator):
    from infra import GenshinApiClient
    from services import GenshinService

    http = FakeHttpClient({"https://genshin.jmp.blue/characters/x": {"name": "X", "rarity": 4}})
    service = GenshinService(GenshinApiClient(http), GenshinMapper(stat_generator))

    service.create_character("x")
    service.create_character("x")

    assert http.requested.count("https://genshin.jmp.blue/characters/x") == 1


def test_each_created_character_is_independent(genshin_service):
    first = genshin_service.create_character("bennett")
    second = genshin_service.create_character("bennett")

    first.take_damage(50, ignore_armor=True)

    assert first is not second
    assert second.health == second.max_health


def test_service_equips_weapon_matching_type(genshin_service):
    albedo = genshin_service.create_character("albedo")
    attack_before = albedo.attack_power

    blade = genshin_service.create_weapon("skyward-blade")
    albedo.equip(blade)

    assert albedo.attack_power == attack_before + 8


def test_service_propagates_unknown_slug(genshin_service):
    with pytest.raises(RemoteServiceError):
        genshin_service.create_character("nobody")


def test_service_filters_lists(genshin_service):
    assert genshin_service.list_characters("ben") == ["bennett"]
    assert genshin_service.list_weapons() == [
        "favonius-sword", "serpent-spine", "skyward-blade", "the-catch", "wolf-s-gravestone",
    ]


# -- CharacterSheetBuilder (structured-text representation) -----------------------------


@pytest.fixture
def equipped_albedo(genshin_service):
    albedo = genshin_service.create_character("albedo")
    albedo.equip(genshin_service.create_weapon("skyward-blade"))
    return albedo


def test_sheet_is_a_text_document_with_character_heading(equipped_albedo):
    sheet = CharacterSheetBuilder().build(equipped_albedo)

    top = sheet.children[0]
    assert isinstance(top, Heading)
    assert top.title == "Albedo"
    assert top.level == 1


def test_sheet_table_of_contents_lists_sections_and_talents(equipped_albedo):
    toc = CharacterSheetBuilder().build(equipped_albedo).table_of_contents()

    assert toc.splitlines() == [
        "- Albedo",
        "  - Stats",
        "  - Talents",
        "    - Favonius Bladework - Weiss",
        "    - Abiogenesis: Solar Isotoma",
        "    - Rite of Progeniture: Tectonic Tide",
        "  - Equipment",
        "    - Skyward Blade",
    ]


def test_sheet_render_contains_current_state(equipped_albedo):
    equipped_albedo.take_damage(30, ignore_armor=True)

    text = CharacterSheetBuilder().build(equipped_albedo).render()

    assert f"HP: {equipped_albedo.health}/{equipped_albedo.max_health}" in text
    assert "Kreideprinz · Geo · Sword · ★★★★★" in text
    assert "Sky-Piercing Fang" in text


def test_sheet_without_equipment_says_so(genshin_service):
    bennett = genshin_service.create_character("bennett")

    text = CharacterSheetBuilder().build(bennett).render()

    assert "(nothing equipped)" in text


def test_sheet_works_for_plain_non_api_character():
    plain = Character(CharacterData("Bob", 50, 50, 1, 5))

    text = CharacterSheetBuilder().build(plain).render()

    assert text.startswith("# Bob")
