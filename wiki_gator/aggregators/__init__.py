"""Aggregator strategies."""

from .base import Aggregator
from .numeric import AverageAggregator, SumAggregator, MinAggregator, MaxAggregator

__all__ = [
    "Aggregator",
    "AverageAggregator",
    "SumAggregator",
    "MinAggregator",
    "MaxAggregator",
]
