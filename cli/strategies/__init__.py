"""Command strategies the CLI facade is parametrised with."""

from .catalog_info import CatalogInfoStrategy
from .catalog_actions import CatalogActionStrategy
from .infrastructure import DatabaseStrategy, StorageStrategy
from .game import BattleStrategy, GameStrategy

__all__ = ["CatalogInfoStrategy", "CatalogActionStrategy", "DatabaseStrategy",
           "StorageStrategy", "GameStrategy", "BattleStrategy"]
