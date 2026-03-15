"""Date-related transform implementations."""

import re
from datetime import date, datetime
from typing import Any

from .base import Transform


class DateToAgeTransform(Transform):
    """Transforms a date to an age (years from reference date).

    For living persons: calculates current age.
    For deceased: can optionally use death date to calculate age at death.
    """

    def __init__(
        self, reference_date: date | None = None, death_date_value: Any = None
    ):
        """Initialize the transform.

        Args:
            reference_date: The date to calculate age from.
                           Defaults to today.
            death_date_value: If provided, calculate age at death
                             instead of current age.
        """
        self.reference_date = reference_date or date.today()
        self.death_date_value = death_date_value

    @property
    def name(self) -> str:
        return "Date to Age"

    def transform(self, raw_value: Any) -> float | None:
        """Transform a date value to age in years.

        Args:
            raw_value: A date in various formats:
                      - Wikidata time format: "+1965-03-15T00:00:00Z"
                      - ISO date string: "1965-03-15"
                      - datetime object
                      - date object

        Returns:
            Age in years (as float), or None if parsing fails.
        """
        birth_date = self._parse_date(raw_value)
        if birth_date is None:
            return None

        # Determine the reference date (death date if provided, else today)
        if self.death_date_value is not None:
            end_date = self._parse_date(self.death_date_value)
            if end_date is None:
                end_date = self.reference_date
        else:
            end_date = self.reference_date

        # Calculate age
        age = self._calculate_age(birth_date, end_date)
        return age

    def _parse_date(self, value: Any) -> date | None:
        """Parse various date formats to a date object."""
        if value is None:
            return None

        if isinstance(value, date):
            return value

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, str):
            # Wikidata format: "+1965-03-15T00:00:00Z"
            wikidata_match = re.match(r"[+-]?(\d{4})-(\d{2})-(\d{2})", value)
            if wikidata_match:
                try:
                    year = int(wikidata_match.group(1))
                    month = int(wikidata_match.group(2))
                    day = int(wikidata_match.group(3))

                    # Handle incomplete dates (month=0 or day=0)
                    if month == 0:
                        month = 1
                    if day == 0:
                        day = 1

                    return date(year, month, day)
                except ValueError:
                    return None

        return None

    def _calculate_age(self, birth_date: date, end_date: date) -> float:
        """Calculate age in years between two dates."""
        # Calculate exact age considering month and day
        years = end_date.year - birth_date.year

        # Adjust if birthday hasn't occurred yet this year
        if (end_date.month, end_date.day) < (birth_date.month, birth_date.day):
            years -= 1

        return float(years)


class DateToAgeAtDeathTransform(Transform):
    """Transforms birth and death dates to age at death.

    Requires both birth_date and death_date to compute.
    Returns None for living persons (no death date).
    """

    def __init__(self):
        """Initialize the transform."""
        self._current_birth_date: Any = None

    @property
    def name(self) -> str:
        return "Date to Age at Death"

    def set_birth_date(self, birth_date: Any) -> None:
        """Set the birth date for the next transform call."""
        self._current_birth_date = birth_date

    def transform(self, raw_value: Any) -> float | None:
        """Transform death date to age at death.

        Args:
            raw_value: The death date value.

        Returns:
            Age at death in years, or None if either date is missing.
        """
        if self._current_birth_date is None or raw_value is None:
            return None

        inner = DateToAgeTransform(death_date_value=raw_value)
        return inner.transform(self._current_birth_date)


class IdentityTransform(Transform):
    """Returns numeric values as-is (no transformation).

    Use for properties that are already numeric values.
    """

    @property
    def name(self) -> str:
        return "Identity (No Transform)"

    def transform(self, raw_value: Any) -> float | None:
        """Return the value as a float if possible.

        Args:
            raw_value: A numeric value or numeric string.

        Returns:
            The value as a float, or None if not numeric.
        """
        if raw_value is None:
            return None

        if isinstance(raw_value, (int, float)):
            return float(raw_value)

        if isinstance(raw_value, str):
            try:
                return float(raw_value.lstrip("+"))
            except ValueError:
                return None

        return None
