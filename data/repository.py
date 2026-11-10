"""Repository: the Data-layer facade. Serializes the whole application
state (game catalog + text document) to one JSON file and back.

This is deliberately the only place that touches the filesystem for
persistence - CLI code asks Repository to save/load, it never opens
files itself.
"""

from __future__ import annotations

import json
from typing import Any

from core.text import Root, TextFactory

from . import game_serializer, text_serializer


class Repository:
    def save(self, path: str, *, characters, items, abilities, document: Root) -> None:
        payload: dict[str, Any] = {
            "catalog": game_serializer.catalog_to_dict(characters, items, abilities),
            "document": text_serializer.document_to_dict(document),
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def load(self, path: str) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        characters, items, abilities = game_serializer.catalog_from_dict(payload.get("catalog", {}))
        document = text_serializer.dict_to_document(payload.get("document", {"children": []}), TextFactory())

        return {
            "characters": characters,
            "items": items,
            "abilities": abilities,
            "document": document,
        }
