"""Bulbapedia data fetcher implementation."""

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from ..models import Entry
from .base import DataFetcher


class BulbapediaFetcher(DataFetcher):
    """Fetches Pokemon data from raw HTML sections.

    Takes Entry objects with html_content containing trainer/Pokemon HTML,
    parses them to extract Pokemon names and levels, then fetches base
    experience from PokeAPI.
    """

    POKEAPI_URL = "https://pokeapi.co/api/v2/pokemon/{name}"

    def __init__(self, session: requests.Session | None = None):
        """Initialize the fetcher.

        Args:
            session: Optional requests session for connection pooling.
        """
        self.session = session or requests.Session()
        # Cache for Pokemon name -> base experience
        self._base_exp_cache: dict[str, int | None] = {}

    def fetch(self, entry: Entry, property_id: str) -> Any:
        """Fetch property for a single entry."""
        result = self.fetch_batch([entry], property_id)
        return result.get(entry.name)

    def fetch_batch(self, entries: list[Entry], property_id: str) -> dict[str, Any]:
        """Extract Pokemon from HTML sections and fetch base experience.

        For entries with html_content, parses the HTML to find Pokemon
        and their levels, then fetches base_exp from PokeAPI.

        Args:
            entries: List of Entry objects with html_content.
            property_id: Property to fetch (e.g., "base_exp").

        Returns:
            Dict mapping entry name to list of Pokemon dicts with
            name, level, and base_exp.
        """
        results: dict[str, Any] = {}

        # First pass: extract all Pokemon from HTML and collect unique names
        entry_pokemon: dict[str, list[dict]] = {}
        unique_pokemon_names: set[str] = set()

        for entry in entries:
            pokemon_list = self._extract_pokemon_from_html(entry.html_content)
            entry_pokemon[entry.name] = pokemon_list

            for pokemon in pokemon_list:
                name = pokemon.get("name")
                if name and name.lower() not in self._base_exp_cache:
                    unique_pokemon_names.add(name)

        # Fetch base_exp for all unique Pokemon from PokeAPI
        for pokemon_name in unique_pokemon_names:
            base_exp = self._fetch_base_exp_from_api(pokemon_name)
            self._base_exp_cache[pokemon_name.lower()] = base_exp

        # Build results with populated base_exp
        for entry in entries:
            pokemon_list = entry_pokemon.get(entry.name, [])
            enriched_pokemon = []

            for pokemon in pokemon_list:
                pokemon_name = pokemon.get("name")
                base_exp = (
                    self._base_exp_cache.get(pokemon_name.lower())
                    if pokemon_name
                    else None
                )

                enriched_pokemon.append(
                    {
                        **pokemon,
                        "base_exp": base_exp,
                    }
                )

            results[entry.name] = enriched_pokemon
            # Set on entry's raw_value for transform processing
            entry.raw_value = enriched_pokemon

        return results

    def _extract_pokemon_from_html(self, html_content: str | None) -> list[dict]:
        """Extract Pokemon names and levels from HTML content.

        Handles Bulbapedia partybox format and table formats.

        Args:
            html_content: Raw HTML string containing Pokemon data.

        Returns:
            List of dicts with 'name' and 'level' keys.
        """
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        pokemon_list = []

        # Method 1: Partybox format (modern Bulbapedia)
        # Look for PKMNbox elements containing Pokemon data
        for pkmn_box in soup.find_all(class_=re.compile(r"PKMNbox")):
            pokemon = self._extract_from_pkmnbox(pkmn_box)
            if pokemon:
                pokemon_list.append(pokemon)

        # If no partybox found, try table format
        if not pokemon_list:
            pokemon_list = self._extract_from_table(soup)

        return pokemon_list

    def _extract_from_pkmnbox(self, box: BeautifulSoup) -> dict | None:
        """Extract Pokemon data from a PKMNbox element."""
        # Find Pokemon name from link
        name_link = box.find(
            "a", title=lambda t: t and "(Pokémon)" in t if t else False
        )
        if not name_link:
            # Try finding any Pokemon-related link
            name_link = box.find("a", href=re.compile(r"/wiki/.*_\(Pok"))

        if not name_link:
            return None

        # Extract name from link text or title
        name = name_link.get_text(strip=True)
        if not name:
            title = name_link.get("title", "")
            name = re.sub(r"\s*\(Pokémon\)", "", title)

        # Find level
        level = None
        level_elem = box.find(class_=re.compile(r"PKMNlevel|level"))
        if level_elem:
            level_text = level_elem.get_text(strip=True)
            level_match = re.search(r"(\d+)", level_text)
            if level_match:
                level = int(level_match.group(1))

        # Fallback: look for "Lv." or "Level" text
        if level is None:
            box_text = box.get_text()
            level_match = re.search(r"L(?:v\.?|evel)\s*(\d+)", box_text, re.I)
            if level_match:
                level = int(level_match.group(1))

        if name and level is not None:
            return {"name": name, "level": level}

        return None

    def _extract_from_table(self, soup: BeautifulSoup) -> list[dict]:
        """Extract Pokemon data from table format."""
        pokemon_list = []

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            # Look for Pokemon link and level in the row
            pokemon_link = row.find("a", href=re.compile(r"/wiki/.*_\(Pok"))
            if not pokemon_link:
                continue

            name = pokemon_link.get_text(strip=True)

            # Find level in the row
            row_text = row.get_text()
            level_match = re.search(r"L(?:v\.?|evel)\s*(\d+)", row_text, re.I)
            if level_match:
                level = int(level_match.group(1))
                pokemon_list.append({"name": name, "level": level})

        return pokemon_list

    def _fetch_base_exp_from_api(self, pokemon_name: str) -> int | None:
        """Fetch base experience from PokeAPI.

        Args:
            pokemon_name: Name of the Pokemon (e.g., "Pikachu").

        Returns:
            Base experience value, or None if not found.
        """
        api_name = self._normalize_for_api(pokemon_name)

        try:
            url = self.POKEAPI_URL.format(name=api_name)
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("base_experience")
            return None

        except requests.RequestException:
            return None

    def _normalize_for_api(self, pokemon_name: str) -> str:
        """Normalize Pokemon name for PokeAPI lookup.

        PokeAPI uses lowercase, hyphenated names.
        """
        name = pokemon_name.lower().strip()

        # Handle special characters
        name = name.replace("♀", "-f").replace("♂", "-m")
        name = name.replace("'", "").replace("'", "")
        name = name.replace(". ", "-").replace(".", "")
        name = name.replace(" ", "-")

        # Remove any remaining non-alphanumeric except hyphen
        name = re.sub(r"[^a-z0-9\-]", "", name)

        return name
