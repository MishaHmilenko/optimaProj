"""CLI: the `db` and `sheet` commands, wired to the offline
FileHttpClient so tests never touch the network."""

import pytest

def test_db_chars_lists_slugs(chars):
    out = chars.run("db chars")
    for slug in ("albedo", "bennett", "diluc", "xiangling"):
        assert slug in out


def test_db_weapons_filter(chars):
    out = chars.run("db weapons --filter sword")
    assert "favonius-sword" in out
    assert "the-catch" not in out


def test_db_show_character(chars):
    out = chars.run("db show char diluc")
    assert "Diluc" in out and "Claymore" in out


def test_db_create_adds_virtual_character_to_catalog(chars):
    out = chars.run("db create albedo")

    assert chars.catalog.find_character("c1").name == "Albedo"
    assert "[c1]" in out


def test_db_equip_adds_weapon_and_equips_it(chars):
    chars.run("db create albedo")
    attack_before = chars.catalog.find_character("c1").attack_power

    chars.run("db equip c1 skyward-blade")

    albedo = chars.catalog.find_character("c1")
    assert [item.name for item in albedo.equipment] == ["Skyward Blade"]
    assert albedo.attack_power == attack_before + 8
    assert chars.catalog.find_item("i1") is albedo.equipment[0]


def test_db_equip_rejects_wrong_weapon_type(chars):
    chars.run("db create albedo")

    out = chars.run("db equip c1 wolf-s-gravestone")

    assert chars.catalog.find_character("c1").equipment == ()
    assert "cannot equip" in out.lower()


def test_db_create_unknown_slug_reports_error(chars):
    out = chars.run("db create nobody")

    assert chars.catalog.find_character("c1") is None
    assert "404" in out


def test_db_without_subcommand_lists_subcommands(chars):
    out = chars.run("db")

    for sub in ("refresh", "chars", "weapons", "show", "create", "equip"):
        assert f"db {sub}" in out


def test_db_refresh_loads_details_with_progress_and_table(chars):
    out = chars.run("db refresh")

    assert "4/4" in out and "4 character(s) loaded" in out
    table = chars.run("db chars")
    assert "Vision" in table and "Geo" in table and "Liyue" in table


def test_db_show_includes_artwork_links(chars):
    out = chars.run("db show char albedo")

    assert "https://genshin.jmp.blue/characters/albedo/icon-big" in out
    assert "/albedo/card" in out


def test_show_catalog_character_has_stats_and_links(chars):
    chars.run("db create diluc")

    out = chars.run("show c1")

    assert "Diluc" in out and "HP" in out and "Claymore" in out
    assert "/characters/diluc/gacha-splash" in out


def test_sheet_writes_rendered_document(chars):
    chars.run("db create xiangling")
    chars.run("db equip c1 the-catch")

    out = chars.run("sheet c1")

    assert out.startswith("# Xiangling")
    assert "## Equipment" in out
    assert "### The Catch" in out


def test_sheet_toc_option(chars):
    chars.run("db create bennett")

    out = chars.run("sheet c1 --toc")

    assert out.splitlines()[0] == "- Bennett"


def test_api_characters_work_with_existing_combat_commands(chars):
    chars.run("db create albedo")
    chars.run("db create diluc")
    diluc = chars.catalog.find_character("c2")
    health_before = diluc.health

    out = chars.run('act ability c1 c2 --id "Abiogenesis: Solar Isotoma"')

    assert diluc.health < health_before
    assert "Abiogenesis" in out


def test_api_characters_survive_save_and_load(chars, tmp_path):
    chars.run("db create xiangling")
    chars.run("db equip c1 the-catch")
    original = chars.catalog.find_character("c1")
    path = tmp_path / "state.json"
    chars.run(f"save {path}")

    chars.run(f"load {path}")

    restored = chars.catalog.find_character("c1")
    assert restored is not original
    assert restored.data == original.data
    assert restored.get_ability("Pyronado").talent_type == "ELEMENTAL_BURST"
    assert [i.name for i in restored.equipment] == ["The Catch"]
    assert restored.data.images["card"].endswith("/characters/xiangling/card")
