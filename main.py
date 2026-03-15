#!/usr/bin/env python3
"""CLI entry point for WikiGator."""

import argparse
import sys

from wiki_gator import WikiGator
from wiki_gator.aggregators import AverageAggregator
from wiki_gator.extractors import WikipediaListExtractor
from wiki_gator.fetchers import WikidataFetcher
from wiki_gator.output import CSVWriter
from wiki_gator.transforms import DateToAgeTransform


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="Analyze Wikipedia 'List of' pages and compute aggregate statistics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compute average age of US playwrights by letter
  python main.py "https://en.wikipedia.org/wiki/List_of_playwrights_from_the_United_States" --level 2

  # Compute average age of US presidents
  python main.py "https://en.wikipedia.org/wiki/List_of_presidents_of_the_United_States" --level 2

  # Use a custom Wikidata property
  python main.py "https://en.wikipedia.org/wiki/List_of_..." --property P569 --level 2

Common Wikidata properties:
  P569  - Date of birth
  P570  - Date of death
  P2048 - Height
  P2067 - Mass
        """,
    )

    parser.add_argument(
        "url",
        help="URL of the Wikipedia 'List of' page to analyze",
    )

    parser.add_argument(
        "--level",
        "-l",
        type=int,
        default=2,
        help="Heading level for section grouping (2=H2, 3=H3, etc.). Default: 2",
    )

    parser.add_argument(
        "--output",
        "-o",
        default="output.csv",
        help="Output CSV file path. Default: output.csv",
    )

    parser.add_argument(
        "--property",
        "-p",
        default="P569",
        help="Wikidata property ID to fetch. Default: P569 (birth date)",
    )

    parser.add_argument(
        "--death-property",
        default="P570",
        help="Wikidata property ID for death date (for age calculation). Default: P570",
    )

    parser.add_argument(
        "--no-death-date",
        action="store_true",
        help="Don't use death dates for age calculation (use current date only)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Output additional debug CSV with per-entry data",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )

    return parser


def progress_printer(quiet: bool):
    """Create a progress callback function."""

    def callback(message: str) -> None:
        if not quiet:
            print(f"  {message}")

    return callback


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.quiet:
        print(f"WikiGator")
        print(f"=" * 40)
        print(f"URL: {args.url}")
        print(f"Section level: H{args.level}")
        print(f"Property: {args.property}")
        print()

    # Create strategy instances
    extractor = WikipediaListExtractor()
    fetcher = WikidataFetcher()
    transform = DateToAgeTransform()
    aggregator = AverageAggregator()

    # Create analyzer
    analyzer = WikiGator(
        extractor=extractor,
        fetcher=fetcher,
        transform=transform,
        aggregator=aggregator,
        progress_callback=progress_printer(args.quiet),
    )

    # Determine death property usage
    death_property = None if args.no_death_date else args.death_property

    try:
        # Run analysis
        results = analyzer.analyze(
            url=args.url,
            level=args.level,
            property_id=args.property,
            death_property_id=death_property,
        )

        # Write output
        writer = CSVWriter(args.output)
        if args.debug:
            writer.write_with_debug(results)
            if not args.quiet:
                print(
                    f"\nDebug output written to: {args.output.replace('.csv', '.debug.csv')}"
                )
        else:
            writer.write(results)

        if not args.quiet:
            print(f"\nResults written to: {args.output}")
            print()

            # Print summary
            total_count = sum(r.count for r in results)
            total_skipped = sum(r.skipped_count for r in results)
            print(f"Summary:")
            print(f"  Sections analyzed: {len(results)}")
            print(f"  Entries with data: {total_count}")
            print(f"  Entries skipped:   {total_skipped}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if not args.quiet:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
