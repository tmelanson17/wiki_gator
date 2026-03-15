"""Data models for wiki analysis."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entry:
    """A single entry extracted from a wiki list.

    Supports both URL-based entries (e.g., Wikipedia articles) and
    HTML-based entries (e.g., embedded trainer data on Bulbapedia).

    Attributes:
        name: Display name of the entry.
        url: Optional URL to the entry's wiki page.
        html_content: Optional HTML string for embedded entries.
        metadata: Optional dict for additional entry-specific data
                 (e.g., Pokemon levels, trainer class).
        raw_value: The raw attribute value fetched from the data source.
        computed_value: The transformed numeric value (for aggregation).
    """

    name: str
    url: str | None = None
    html_content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_value: Any = None
    computed_value: float | None = None


@dataclass
class EntryList:
    """A collection of entries within a section.

    Represents entries found in a particular list format (e.g., bullet list,
    table rows) within a wiki section.
    """

    entries: list[Entry] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)


@dataclass
class Section:
    """A section of a wiki page containing one or more entry lists.

    Attributes:
        name: The section header text.
        level: The heading level (2 for H2, 3 for H3, etc.).
        lists: Collection of entry lists found in this section.
    """

    name: str
    level: int
    lists: list[EntryList] = field(default_factory=list)

    @property
    def all_entries(self) -> list[Entry]:
        """Flatten all entries from all lists in this section."""
        return [entry for lst in self.lists for entry in lst.entries]


@dataclass
class SectionResult:
    """Aggregated result for a section.

    Attributes:
        section_name: The name of the section.
        aggregated_value: The computed aggregate (e.g., average age).
        count: Number of entries with valid computed values.
        skipped_count: Number of entries skipped due to missing data.
        entries: List of entries for debugging (with URLs and values).
    """

    section_name: str
    aggregated_value: float | None
    count: int
    skipped_count: int
    entries: list[Entry] = field(default_factory=list)
