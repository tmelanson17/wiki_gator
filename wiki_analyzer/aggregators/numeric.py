"""Numeric aggregator implementations."""

from .base import Aggregator


class AverageAggregator(Aggregator):
    """Computes the arithmetic mean of values."""

    @property
    def name(self) -> str:
        return "Average"

    def aggregate(self, values: list[float]) -> float | None:
        """Compute the average of the values.

        Args:
            values: List of numeric values.

        Returns:
            The arithmetic mean, or None if the list is empty.
        """
        if not values:
            return None
        return sum(values) / len(values)


class SumAggregator(Aggregator):
    """Computes the sum of values."""

    @property
    def name(self) -> str:
        return "Sum"

    def aggregate(self, values: list[float]) -> float | None:
        """Compute the sum of the values.

        Args:
            values: List of numeric values.

        Returns:
            The sum, or 0.0 if the list is empty.
        """
        return sum(values) if values else 0.0


class MinAggregator(Aggregator):
    """Finds the minimum value."""

    @property
    def name(self) -> str:
        return "Minimum"

    def aggregate(self, values: list[float]) -> float | None:
        """Find the minimum value.

        Args:
            values: List of numeric values.

        Returns:
            The minimum value, or None if the list is empty.
        """
        if not values:
            return None
        return min(values)


class MaxAggregator(Aggregator):
    """Finds the maximum value."""

    @property
    def name(self) -> str:
        return "Maximum"

    def aggregate(self, values: list[float]) -> float | None:
        """Find the maximum value.

        Args:
            values: List of numeric values.

        Returns:
            The maximum value, or None if the list is empty.
        """
        if not values:
            return None
        return max(values)
