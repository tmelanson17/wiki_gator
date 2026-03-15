"""WikiGator - Extensible wiki data extraction and analysis."""

from .models import Entry, EntryList, Section, SectionResult
from .analyzer import WikiGator

__all__ = [
    "Entry",
    "EntryList",
    "Section",
    "SectionResult",
    "WikiGator",
]
