"""Base class for list extractors."""

from abc import ABC, abstractmethod

from ..models import Section


class ListExtractor(ABC):
    """Abstract base class for extracting entries from wiki pages.

    Implementations handle parsing wiki page structure to identify
    sections and extract entry links within each section.
    """

    @abstractmethod
    def extract(self, url: str, level: int) -> list[Section]:
        """Extract sections and entries from a wiki page.

        Args:
            url: The URL of the wiki "list of" page.
            level: The heading level to use for section grouping
                   (2 for H2, 3 for H3, etc.).

        Returns:
            List of Section objects, each containing EntryLists
            with Entry objects (URL and name populated).
        """
        pass
