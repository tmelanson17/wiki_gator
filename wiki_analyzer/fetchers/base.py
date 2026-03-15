"""Base class for data fetchers."""

from abc import ABC, abstractmethod
from typing import Any

from ..models import Entry


class DataFetcher(ABC):
    """Abstract base class for fetching attribute data.

    Implementations handle retrieving specific attribute values
    from data sources (e.g., Wikidata, custom APIs).
    """

    @abstractmethod
    def fetch(self, entry: Entry, property_id: str) -> Any:
        """Fetch a property value for an entry.

        Args:
            entry: The Entry object (with URL populated).
            property_id: The identifier for the property to fetch
                        (e.g., "P569" for birth date in Wikidata).

        Returns:
            The raw property value, or None if not found.
        """
        pass

    @abstractmethod
    def fetch_batch(self, entries: list[Entry], property_id: str) -> dict[str, Any]:
        """Fetch property values for multiple entries.

        Args:
            entries: List of Entry objects.
            property_id: The property identifier to fetch.

        Returns:
            Dictionary mapping entry URLs to raw property values.
        """
        pass
