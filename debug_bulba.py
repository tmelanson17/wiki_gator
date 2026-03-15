"""Test Bulbapedia extractor and data fetcher."""

from wiki_gator.extractors import BulbapediaListExtractor
from wiki_gator.fetchers.bulbapedia import BulbapediaFetcher
from wiki_gator.transforms import ExpYieldTransform

# Test with Generation I (which has partybox format)
extractor = BulbapediaListExtractor(generation_filter="Generation I")
sections = extractor.extract(
    "https://bulbapedia.bulbagarden.net/wiki/Mt._Moon", level=3
)

print(f"Found {len(sections)} sections")

# Test the fetcher (parses HTML and fetches base_exp from PokeAPI)
fetcher = BulbapediaFetcher()
transform = ExpYieldTransform()

for section in sections:
    print(f"\nSection: {section.name}")
    for entry in section.all_entries[:2]:  # Limit for testing
        print(f"  Trainer: {entry.name}")
        print(
            f"  HTML length: {len(entry.html_content) if entry.html_content else 0} chars"
        )

        # Fetch Pokemon data (parses HTML + fetches base_exp)
        fetcher.fetch(entry, "base_exp")

        if entry.raw_value:
            print(f"  Pokemon: {[p['name'] for p in entry.raw_value]}")

            # Apply transform to calculate total EXP
            total_exp = transform.transform(entry.raw_value)
            print(f"  Total EXP yield: {total_exp}")

            # Show breakdown
            for p in entry.raw_value[:3]:
                print(
                    f"    - {p['name']} Lv{p.get('level')}: base={p.get('base_exp')} -> yield={(p.get('base_exp', 0) or 0) * (p.get('level', 0) or 0) / 7:.1f}"
                )
