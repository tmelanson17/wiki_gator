"""EXP yield transform for Bulbapedia Pokemon data."""

import re
from typing import Any

from .base import Transform


class ExpYieldTransform(Transform):
    """Calculates total EXP yield for a trainer's Pokemon team.

    Uses the Generation I-IV formula: (base_exp × level) / 7

    Takes raw_value as a list of Pokemon dicts with name, level, and base_exp.
    The base_exp should already be populated by the BulbapediaFetcher.
    """

    @property
    def name(self) -> str:
        return "EXP Yield"

    def transform(self, raw_value: Any) -> float | None:
        """Calculate total EXP yield for a trainer's Pokemon team.

        Args:
            raw_value: List of Pokemon dicts with 'name', 'level', and 'base_exp'.
                       Example: [{"name": "Pikachu", "level": 25, "base_exp": 112}, ...]

        Returns:
            Total EXP yield as float, or None if no valid Pokemon.
        """
        if not raw_value or not isinstance(raw_value, list):
            return None

        total_exp = 0.0
        valid_count = 0

        for pokemon in raw_value:
            if not isinstance(pokemon, dict):
                continue

            level = pokemon.get("level")
            base_exp = pokemon.get("base_exp")

            if level is None or base_exp is None:
                continue

            # Gen I-IV formula: (base_exp × level) / 7
            exp_yield = (base_exp * level) / 7
            total_exp += exp_yield
            valid_count += 1

        return round(total_exp, 2) if valid_count > 0 else None
