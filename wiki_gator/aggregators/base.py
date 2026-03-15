"""Base class for aggregators."""

from abc import ABC, abstractmethod


class Aggregator(ABC):
    """Abstract base class for value aggregation.

    Aggregators combine a list of numeric values into
    a single summary statistic.
    """

    @abstractmethod
    def aggregate(self, values: list[float]) -> float | None:
        """Aggregate a list of values to a single value.

        Args:
            values: List of numeric values to aggregate.
                   May be empty.

        Returns:
            The aggregated value, or None if aggregation
            is not possible (e.g., empty list for average).
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this aggregator."""
        pass
