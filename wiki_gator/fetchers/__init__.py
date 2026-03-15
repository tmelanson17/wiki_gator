"""Data fetcher strategies."""

from .base import DataFetcher
from .wikidata import WikidataFetcher
from .bulbapedia import BulbapediaFetcher

__all__ = ["DataFetcher", "WikidataFetcher", "BulbapediaFetcher"]
