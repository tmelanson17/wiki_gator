"""CSV output writer."""

import csv
from pathlib import Path

from ..models import SectionResult


class CSVWriter:
    """Writes section results to CSV format."""

    def __init__(self, output_path: str | Path, value_label: str = "Average Age"):
        """Initialize the writer.

        Args:
            output_path: Path to the output CSV file.
            value_label: Column header for the aggregated value.
        """
        self.output_path = Path(output_path)
        self.value_label = value_label

    def write(self, results: list[SectionResult]) -> None:
        """Write section results to a CSV file.

        Args:
            results: List of SectionResult objects to write.

        Creates columns: Section, Average Age, Count, Skipped Count
        """
        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(["Section", self.value_label, "Count", "Skipped Count"])

            # Write data rows
            for result in results:
                avg_value = (
                    f"{result.aggregated_value:.1f}"
                    if result.aggregated_value is not None
                    else "N/A"
                )
                writer.writerow(
                    [result.section_name, avg_value, result.count, result.skipped_count]
                )

    def write_with_debug(self, results: list[SectionResult]) -> None:
        """Write section results with per-entry debug info.

        Creates an additional CSV with individual entry data.
        """
        # Write summary CSV
        self.write(results)

        # Write detailed debug CSV
        debug_path = self.output_path.with_suffix(".debug.csv")
        with open(debug_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow(["Section", "Entry Name", "Entry URL", "Computed Value"])

            for result in results:
                for entry in result.entries:
                    computed = (
                        f"{entry.computed_value:.1f}"
                        if entry.computed_value is not None
                        else "N/A"
                    )
                    writer.writerow(
                        [result.section_name, entry.name, entry.url, computed]
                    )
