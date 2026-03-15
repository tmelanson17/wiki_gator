"""Bulbapedia list extractor implementation."""

import re

import requests
from bs4 import BeautifulSoup, Tag

from ..models import Entry, EntryList, Section
from .base import ListExtractor


class BulbapediaListExtractor(ListExtractor):
    """Extracts trainer entries from Bulbapedia location pages.

    Parses the HTML structure of Bulbapedia pages to identify
    trainer sections by generation and extract trainer party data.

    Supports two formats:
    - Partybox format: Modern collapsible trainer boxes
    - Table format: Older table-based trainer listings
    """

    BASE_URL = "https://bulbapedia.bulbagarden.net"

    def __init__(
        self,
        session: requests.Session | None = None,
        generation_filter: str | None = "Generation III",
    ):
        """Initialize the extractor.

        Args:
            session: Optional requests session for connection pooling.
            generation_filter: Filter trainers by generation header.
                              None means extract all generations.
                              Default: "Generation III"
        """
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": "WikiAnalyzer/1.0 (Educational/Research Tool)"}
        )
        self.generation_filter = generation_filter

    def extract(self, url: str, level: int) -> list[Section]:
        """Extract trainer sections from a Bulbapedia page.

        Args:
            url: The Bulbapedia URL (e.g., https://bulbapedia.bulbagarden.net/wiki/Mt._Moon).
            level: Heading level for section grouping (typically 3 for generation headers).

        Returns:
            List of Section objects with trainer entries.
            Each Entry contains the trainer's HTML content and metadata.
        """
        response = self.session.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.find("div", {"class": "mw-parser-output"})

        if not content:
            return []

        sections = []

        # Find the Trainers h2 section
        trainers_section = self._find_trainers_section(content)
        if not trainers_section:
            # Fallback: try to find partyboxes anywhere
            return self._extract_partybox_sections(content, level)

        # Extract trainers organized by generation
        sections = self._extract_by_generation(content, trainers_section, level)

        return sections

    def _find_trainers_section(self, content: Tag) -> Tag | None:
        """Find the Trainers h2 heading."""
        for h2 in content.find_all("h2"):
            if "Trainer" in h2.get_text():
                return h2
        return None

    def _extract_by_generation(
        self, content: Tag, trainers_h2: Tag, level: int
    ) -> list[Section]:
        """Extract trainers grouped by generation headers."""
        sections = []

        # Get all partyboxes with their generation context
        partyboxes = content.find_all("div", class_="partybox")

        for partybox in partyboxes:
            # Find the preceding generation h3
            prev_h3 = partybox.find_previous("h3")
            if not prev_h3:
                continue

            gen_text = prev_h3.get_text(strip=True)

            # Apply generation filter if set
            if self.generation_filter and self.generation_filter not in gen_text:
                continue

            # Find or create section for this generation
            section = next((s for s in sections if s.name == gen_text), None)
            if not section:
                section = Section(name=gen_text, level=level, lists=[EntryList()])
                sections.append(section)

            # Extract trainer entry from partybox
            entry = self._parse_partybox(partybox)
            if entry:
                section.lists[0].entries.append(entry)

        # Also check for table-based trainers
        table_sections = self._extract_table_trainers(content, level)

        # Merge table sections with partybox sections
        for table_section in table_sections:
            existing = next((s for s in sections if s.name == table_section.name), None)
            if existing:
                existing.lists.extend(table_section.lists)
            else:
                sections.append(table_section)

        return sections

    def _parse_partybox(self, partybox: Tag) -> Entry | None:
        """Parse a partybox div into an Entry with HTML content.

        The HTML content will be parsed by the DataFetcher to extract
        Pokemon names, levels, and base experience.
        """
        # Get trainer name
        name_div = partybox.find("div", class_="partyname")
        trainer_name = name_div.get_text(strip=True) if name_div else "Unknown Trainer"

        # Get the Pokemon HTML section
        pokemon_div = partybox.find("div", class_="partypokemon")
        if not pokemon_div:
            return None

        # Create entry with raw HTML content
        entry = Entry(
            name=trainer_name,
            html_content=str(pokemon_div),
            metadata={"format": "partybox"},
        )

        return entry

    def _extract_table_trainers(self, content: Tag, level: int) -> list[Section]:
        """Extract trainers from table format (older style)."""
        sections = []

        # Find tables with "Trainer" and "Pokémon" headers
        for table in content.find_all("table"):
            first_row = table.find("tr")
            if not first_row:
                continue

            header_text = first_row.get_text(strip=True)
            if "Trainer" not in header_text or "Pokémon" not in header_text:
                continue

            # Find the preceding generation h3
            prev_h3 = table.find_previous("h3")
            if not prev_h3:
                continue

            gen_text = prev_h3.get_text(strip=True)

            # Apply generation filter
            if self.generation_filter and self.generation_filter not in gen_text:
                continue

            # Extract trainers from table rows
            entries = self._parse_trainer_table(table)

            if entries:
                section = Section(
                    name=gen_text, level=level, lists=[EntryList(entries=entries)]
                )
                sections.append(section)

        return sections

    def _parse_trainer_table(self, table: Tag) -> list[Entry]:
        """Parse a trainer table to extract entries with raw HTML."""
        entries = []

        rows = table.find_all("tr")
        current_trainer_name = None
        current_row_html = []

        for row in rows[1:]:  # Skip header row
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            # Check if this row has trainer info
            trainer_cell = None
            for cell in cells:
                # Look for trainer class links
                trainer_link = cell.find(
                    "a", href=lambda x: x and "Trainer_class" in str(x)
                )
                if trainer_link:
                    trainer_cell = cell
                    break

            if trainer_cell:
                # Save previous trainer if exists
                if current_trainer_name and current_row_html:
                    entry = Entry(
                        name=current_trainer_name,
                        html_content="\n".join(current_row_html),
                        metadata={"format": "table"},
                    )
                    entries.append(entry)

                # Start new trainer
                current_trainer_name = trainer_cell.get_text(strip=True)
                # Clean up the name (remove reward info, etc.)
                current_trainer_name = re.sub(
                    r"Reward:.*", "", current_trainer_name
                ).strip()
                current_trainer_name = re.sub(
                    r"\$\d+", "", current_trainer_name
                ).strip()
                current_row_html = [str(row)]
            else:
                current_row_html.append(str(row))

        # Don't forget the last trainer
        if current_trainer_name and current_row_html:
            entry = Entry(
                name=current_trainer_name,
                html_content="\n".join(current_row_html),
                metadata={"format": "table"},
            )
            entries.append(entry)

        return entries

    def _extract_partybox_sections(self, content: Tag, level: int) -> list[Section]:
        """Fallback: extract all partyboxes without generation filtering."""
        entries = []

        partyboxes = content.find_all("div", class_="partybox")
        for partybox in partyboxes:
            entry = self._parse_partybox(partybox)
            if entry:
                entries.append(entry)

        if entries:
            return [
                Section(
                    name="Trainers", level=level, lists=[EntryList(entries=entries)]
                )
            ]

        return []
