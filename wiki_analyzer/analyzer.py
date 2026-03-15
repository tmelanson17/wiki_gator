"""Wiki Analyzer orchestrator."""

from datetime import date
from typing import Callable

from .aggregators.base import Aggregator
from .extractors.base import ListExtractor
from .fetchers.base import DataFetcher
from .models import Entry, Section, SectionResult
from .transforms.base import Transform


class WikiAnalyzer:
    """Orchestrates the wiki analysis pipeline.

    Coordinates the extraction, fetching, transformation, and
    aggregation of wiki data.
    """

    def __init__(
        self,
        extractor: ListExtractor,
        fetcher: DataFetcher,
        transform: Transform,
        aggregator: Aggregator,
        progress_callback: Callable[[str], None] | None = None,
    ):
        """Initialize the analyzer.

        Args:
            extractor: Strategy for extracting entries from wiki pages.
            fetcher: Strategy for fetching attribute data.
            transform: Strategy for transforming raw values to numeric.
            aggregator: Strategy for aggregating values per section.
            progress_callback: Optional callback for progress updates.
        """
        self.extractor = extractor
        self.fetcher = fetcher
        self.transform = transform
        self.aggregator = aggregator
        self.progress_callback = progress_callback or (lambda x: None)

    def analyze(
        self,
        url: str,
        level: int,
        property_id: str,
        death_property_id: str | None = None,
    ) -> list[SectionResult]:
        """Analyze a wiki list page and return aggregated results.

        Args:
            url: The URL of the wiki list page.
            level: Heading level for section grouping (2=H2, etc.).
            property_id: The Wikidata property ID to fetch (e.g., "P569").
            death_property_id: Optional death date property for age calculation.

        Returns:
            List of SectionResult objects, one per section.
        """
        # Step 1: Extract sections and entries
        self.progress_callback("Extracting sections from page...")
        sections = self.extractor.extract(url, level)
        self.progress_callback(f"Found {len(sections)} sections")

        # Collect all entries across sections for batch fetching
        all_entries: list[Entry] = []

        for section in sections:
            for entry in section.all_entries:
                all_entries.append(entry)

        self.progress_callback(f"Found {len(all_entries)} total entries")

        # Step 2: Fetch property values (batched)
        # The fetcher returns a dict keyed by entry identifier (URL or name)
        self.progress_callback(f"Fetching {property_id} values...")
        fetched_values = self.fetcher.fetch_batch(all_entries, property_id)

        # Fetch death dates if needed
        fetched_death_values: dict[str, any] = {}
        if death_property_id:
            self.progress_callback(f"Fetching {death_property_id} values...")
            fetched_death_values = self.fetcher.fetch_batch(
                all_entries, death_property_id
            )

        # Step 3: Apply transform and populate entries
        self.progress_callback("Transforming values...")
        for entry in all_entries:
            # Get the entry's key for lookup (URL if available, else name)
            entry_key = entry.url or entry.name

            # If raw_value not already set by fetcher, look it up
            if entry.raw_value is None:
                entry.raw_value = fetched_values.get(entry_key)

            # Handle age calculation with death dates
            if death_property_id:
                death_date = fetched_death_values.get(entry_key)
                entry.computed_value = self._compute_age(entry.raw_value, death_date)
            else:
                entry.computed_value = self.transform.transform(entry.raw_value)

        # Step 4: Aggregate per section
        self.progress_callback("Aggregating results...")
        results: list[SectionResult] = []

        for section in sections:
            entries = section.all_entries
            valid_values = [
                e.computed_value for e in entries if e.computed_value is not None
            ]
            skipped = len(entries) - len(valid_values)

            aggregated = self.aggregator.aggregate(valid_values)

            result = SectionResult(
                section_name=section.name,
                aggregated_value=aggregated,
                count=len(valid_values),
                skipped_count=skipped,
                entries=entries,
            )
            results.append(result)

        self.progress_callback("Analysis complete!")
        return results

    def _compute_age(
        self,
        birth_date: any,
        death_date: any,
    ) -> float | None:
        """Compute age, using death date if available.

        For living persons (no death date), calculates current age.
        For deceased, calculates age at death.
        """
        from .transforms.date_transforms import DateToAgeTransform

        if birth_date is None:
            return None

        # Use death date as reference if available, otherwise today
        transform = DateToAgeTransform(
            reference_date=date.today(),
            death_date_value=death_date,
        )
        return transform.transform(birth_date)
