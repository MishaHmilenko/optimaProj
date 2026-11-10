"""Infra: HTTP clients and the Genshin API client (written test-first)."""

import io
import json
import urllib.error

import pytest

from infra import (
    FileHttpClient,
    GenshinApiClient,
    RemoteServiceError,
    UrllibHttpClient,
)

from .doubles import FakeHttpClient

BASE = "https://genshin.jmp.blue"


# -- UrllibHttpClient (the real network transport, with urlopen mocked) ----------


def test_urllib_client_decodes_json(mocker):
    response = mocker.MagicMock()
    response.__enter__.return_value = io.BytesIO(b'["albedo", "bennett"]')
    urlopen = mocker.patch("infra.http_client.urllib.request.urlopen", return_value=response)

    result = UrllibHttpClient(timeout=3).get_json(f"{BASE}/characters")

    assert result == ["albedo", "bennett"]
    assert urlopen.call_args.kwargs["timeout"] == 3


def test_urllib_client_wraps_network_errors(mocker):
    mocker.patch(
        "infra.http_client.urllib.request.urlopen",
        side_effect=urllib.error.URLError("no route"),
    )

    with pytest.raises(RemoteServiceError):
        UrllibHttpClient().get_json(f"{BASE}/characters")


def test_urllib_client_wraps_invalid_json(mocker):
    response = mocker.MagicMock()
    response.__enter__.return_value = io.BytesIO(b"<html>not json</html>")
    mocker.patch("infra.http_client.urllib.request.urlopen", return_value=response)

    with pytest.raises(RemoteServiceError):
        UrllibHttpClient().get_json(f"{BASE}/characters")


# -- FileHttpClient (offline transport over bundled samples) -------------------------


def test_file_client_maps_url_path_to_json_file(file_http_client):
    result = file_http_client.get_json(f"{BASE}/characters/albedo")

    assert result["name"] == "Albedo"


def test_file_client_raises_for_missing_resource(file_http_client):
    with pytest.raises(RemoteServiceError):
        file_http_client.get_json(f"{BASE}/characters/nobody")


# -- GenshinApiClient ---------------------------------------------------------------


def test_list_characters_requests_characters_endpoint():
    http = FakeHttpClient({f"{BASE}/characters": ["albedo", "bennett"]})

    slugs = GenshinApiClient(http).list_characters()

    assert slugs == ["albedo", "bennett"]
    assert http.requested == [f"{BASE}/characters"]


def test_list_weapons_requests_weapons_endpoint():
    http = FakeHttpClient({f"{BASE}/weapons": ["skyward-blade"]})

    assert GenshinApiClient(http).list_weapons() == ["skyward-blade"]


def test_get_character_parses_dto(genshin_api):
    dto = genshin_api.get_character("albedo")

    assert dto.slug == "albedo"
    assert dto.name == "Albedo"
    assert dto.title == "Kreideprinz"
    assert dto.vision == "Geo"
    assert dto.weapon_type == "Sword"
    assert dto.rarity == 5
    assert dto.nation == "Mondstadt"
    assert [t.type for t in dto.talents] == ["NORMAL_ATTACK", "ELEMENTAL_SKILL", "ELEMENTAL_BURST"]


def test_get_weapon_parses_dto(genshin_api):
    dto = genshin_api.get_weapon("skyward-blade")

    assert dto.name == "Skyward Blade"
    assert dto.type == "Sword"
    assert dto.rarity == 5
    assert dto.base_attack == 44
    assert dto.sub_stat == "Energy Recharge"
    assert dto.passive_name == "Sky-Piercing Fang"


def test_get_character_tolerates_missing_optional_fields():
    http = FakeHttpClient({f"{BASE}/characters/x": {"name": "X", "rarity": 4}})

    dto = GenshinApiClient(http).get_character("x")

    assert dto.name == "X"
    assert dto.vision == ""
    assert dto.talents == ()


def test_custom_base_url_is_used():
    http = FakeHttpClient({"http://local/characters": []})

    GenshinApiClient(http, base_url="http://local/").list_characters()

    assert http.requested == ["http://local/characters"]


def test_slug_is_url_encoded():
    http = FakeHttpClient({f"{BASE}/characters/a%20b": {"name": "AB"}})

    assert GenshinApiClient(http).get_character("a b").name == "AB"


def test_unexpected_list_payload_is_rejected():
    http = FakeHttpClient({f"{BASE}/characters": {"not": "a list"}})

    with pytest.raises(RemoteServiceError):
        GenshinApiClient(http).list_characters()


def test_sample_files_are_valid_json(samples_dir):
    for path in samples_dir.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
