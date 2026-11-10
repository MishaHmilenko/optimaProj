"""Tests for the Data layer: serializers and the JSON Repository."""

import json

from core.game import Character, CharacterData, Fireball, Item, ItemData
from core.text import ElementKind, Heading, Link, TextFactory
from data import Repository, game_serializer, text_serializer


def build_document():
    factory = TextFactory()
    root = factory.create_document()
    intro = factory.create_and_attach(root, ElementKind.HEADING, title="Intro", level=1)
    factory.create_and_attach(intro, ElementKind.PARAGRAPH, text="Body")
    factory.create_and_attach(intro, ElementKind.LINK, label="Docs", url="https://x.y")
    return root


def test_document_round_trip_preserves_rendering():
    original = build_document()

    restored = text_serializer.dict_to_document(text_serializer.document_to_dict(original))

    assert restored.render() == original.render()


def test_document_round_trip_preserves_types_and_parents():
    restored = text_serializer.dict_to_document(text_serializer.document_to_dict(build_document()))

    heading = restored.children[0]
    assert isinstance(heading, Heading)
    assert isinstance(heading.children[1], Link)


def test_document_dict_is_json_serializable():
    payload = text_serializer.document_to_dict(build_document())

    assert json.loads(json.dumps(payload)) == payload


def test_catalog_round_trip_does_not_double_apply_item_bonuses():
    shield = Item(ItemData("Shield", {"armor": 5}))
    knight = Character(CharacterData("Knight", 100, 100, 2, 10))
    knight.equip(shield)

    data = game_serializer.catalog_to_dict([("c1", knight)], [("i1", shield)], [])
    characters, items, _ = game_serializer.catalog_from_dict(data)

    restored = characters[0][1]
    assert restored.armor == 7
    assert [item.name for item in restored.equipment] == ["Shield"]


def test_catalog_round_trip_relinks_abilities_by_name():
    fireball = Fireball(damage=22)
    mage = Character(CharacterData("Mage", 80, 80, 0, 5))
    mage.learn_ability(fireball)

    data = game_serializer.catalog_to_dict([("c1", mage)], [], [("a1", fireball)])
    characters, _, abilities = game_serializer.catalog_from_dict(data)

    restored_mage = characters[0][1]
    restored_fireball = abilities[0][1]
    assert restored_mage.get_ability("Fireball") is restored_fireball


def test_repository_save_and_load(tmp_path):
    path = tmp_path / "state.json"
    hero = Character(CharacterData("Hero", 50, 40, 1, 3))
    repo = Repository()

    repo.save(str(path), characters=[("c1", hero)], items=[], abilities=[], document=build_document())
    state = repo.load(str(path))

    loaded_hero = state["characters"][0][1]
    assert loaded_hero.health == 40
    assert loaded_hero.max_health == 50
    assert state["document"].render() == build_document().render()
