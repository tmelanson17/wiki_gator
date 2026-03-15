"""Data fetcher strategies."""

from .base import DataFetcher
from .wikidata import WikidataFetcher

__all__ = ["DataFetcher", "WikidataFetcher"]
