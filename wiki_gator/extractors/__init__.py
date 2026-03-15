"""List extractor strategies."""

from .base import ListExtractor
from .wikipedia import WikipediaListExtractor

__all__ = ["ListExtractor", "WikipediaListExtractor"]
