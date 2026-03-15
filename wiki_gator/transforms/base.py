"""Base class for transforms."""

from abc import ABC, abstractmethod
from typing import Any


class Transform(ABC):
    """Abstract base class for value transformations.

    Transforms convert raw attribute values (e.g., dates, strings)
    into numeric values suitable for aggregation.
    """

    @abstractmethod
    def transform(self, raw_value: Any) -> float | None:
        """Transform a raw value to a numeric value.

        Args:
            raw_value: The raw value from the data source.

        Returns:
            A numeric value, or None if transformation fails.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this transform."""
        pass
