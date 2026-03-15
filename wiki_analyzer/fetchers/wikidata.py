"""Wikidata fetcher implementation."""

import re
from typing import Any
from urllib.parse import unquote, urlparse

import requests

from ..models import Entry
from .base import DataFetcher


class WikidataFetcher(DataFetcher):
    """Fetches property values from Wikidata.

    Uses the Wikidata API to resolve Wikipedia article URLs to
    Wikidata entities and retrieve property values.
    """

    WIKIDATA_API = "https://www.wikidata.org/w/api.php"
    WIKIPEDIA_API_TEMPLATE = "https://{lang}.wikipedia.org/w/api.php"

    def __init__(self, session: requests.Session | None = None):
        """Initialize the fetcher.

        Args:
            session: Optional requests session for connection pooling.
        """
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": "WikiAnalyzer/1.0 (Educational/Research Tool)"}
        )
        # Cache for Wikipedia title -> Wikidata ID mapping
        self._entity_cache: dict[str, str | None] = {}

    def fetch(self, entry: Entry, property_id: str) -> Any:
        """Fetch a property value for a single entry."""
        result = self.fetch_batch([entry], property_id)
        return result.get(entry.url)

    def fetch_batch(self, entries: list[Entry], property_id: str) -> dict[str, Any]:
        """Fetch property values for multiple entries.

        Uses batched API requests to minimize network calls.
        Only processes entries that have URLs.
        """
        results: dict[str, Any] = {}

        # Group entries by language (Wikipedia domain)
        entries_by_lang: dict[str, list[Entry]] = {}
        for entry in entries:
            if not entry.url:
                continue  # Skip entries without URLs
            lang = self._extract_language(entry.url)
            if lang:
                entries_by_lang.setdefault(lang, []).append(entry)

        # Process each language group
        for lang, lang_entries in entries_by_lang.items():
            # First, resolve Wikipedia titles to Wikidata IDs
            url_to_entity = self._resolve_entities_batch(lang, lang_entries)

            # Collect all entity IDs that need property fetching
            entity_ids = [eid for eid in url_to_entity.values() if eid]

            if entity_ids:
                # Fetch properties for all entities
                entity_to_value = self._fetch_properties_batch(entity_ids, property_id)

                # Map back to URLs
                for entry in lang_entries:
                    entity_id = url_to_entity.get(entry.url)
                    if entity_id:
                        results[entry.url] = entity_to_value.get(entity_id)

        return results

    def _extract_language(self, url: str) -> str | None:
        """Extract Wikipedia language code from URL."""
        parsed = urlparse(url)
        match = re.match(r"(\w+)\.wikipedia\.org", parsed.netloc)
        if match:
            return match.group(1)
        return None

    def _extract_title(self, url: str) -> str | None:
        """Extract article title from Wikipedia URL."""
        parsed = urlparse(url)
        if "/wiki/" in parsed.path:
            title = parsed.path.split("/wiki/")[-1]
            # Decode URL encoding
            return unquote(title).replace("_", " ")
        return None

    def _resolve_entities_batch(
        self, lang: str, entries: list[Entry]
    ) -> dict[str, str | None]:
        """Resolve Wikipedia titles to Wikidata entity IDs."""
        url_to_entity: dict[str, str | None] = {}
        titles_to_fetch: list[tuple[Entry, str]] = []

        # Check cache first
        for entry in entries:
            title = self._extract_title(entry.url)
            if not title:
                url_to_entity[entry.url] = None
                continue

            cache_key = f"{lang}:{title}"
            if cache_key in self._entity_cache:
                url_to_entity[entry.url] = self._entity_cache[cache_key]
            else:
                titles_to_fetch.append((entry, title))

        # Batch fetch uncached titles (50 at a time - API limit)
        batch_size = 50
        for i in range(0, len(titles_to_fetch), batch_size):
            batch = titles_to_fetch[i : i + batch_size]
            titles = [t for _, t in batch]

            api_url = self.WIKIPEDIA_API_TEMPLATE.format(lang=lang)
            params = {
                "action": "query",
                "format": "json",
                "titles": "|".join(titles),
                "prop": "pageprops",
                "ppprop": "wikibase_item",
            }

            try:
                response = self.session.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()

                # Build title -> entity mapping from response
                pages = data.get("query", {}).get("pages", {})
                title_to_entity: dict[str, str | None] = {}

                for page in pages.values():
                    page_title = page.get("title", "")
                    entity_id = page.get("pageprops", {}).get("wikibase_item")
                    title_to_entity[page_title] = entity_id

                # Update cache and results
                for entry, title in batch:
                    # Try exact match or normalized match
                    entity_id = title_to_entity.get(title)
                    if entity_id is None:
                        # Try case-insensitive match
                        for pt, eid in title_to_entity.items():
                            if pt.lower() == title.lower():
                                entity_id = eid
                                break

                    cache_key = f"{lang}:{title}"
                    self._entity_cache[cache_key] = entity_id
                    url_to_entity[entry.url] = entity_id

            except requests.RequestException:
                # On error, mark all in batch as None
                for entry, title in batch:
                    cache_key = f"{lang}:{title}"
                    self._entity_cache[cache_key] = None
                    url_to_entity[entry.url] = None

        return url_to_entity

    def _fetch_properties_batch(
        self, entity_ids: list[str], property_id: str
    ) -> dict[str, Any]:
        """Fetch property values for multiple Wikidata entities."""
        entity_to_value: dict[str, Any] = {}

        # Wikidata API allows 50 entities per request
        batch_size = 50
        for i in range(0, len(entity_ids), batch_size):
            batch = entity_ids[i : i + batch_size]

            params = {
                "action": "wbgetentities",
                "format": "json",
                "ids": "|".join(batch),
                "props": "claims",
                "languages": "en",
            }

            try:
                response = self.session.get(self.WIKIDATA_API, params=params)
                response.raise_for_status()
                data = response.json()

                entities = data.get("entities", {})
                for entity_id, entity_data in entities.items():
                    value = self._extract_property_value(entity_data, property_id)
                    entity_to_value[entity_id] = value

            except requests.RequestException:
                # On error, all entities in batch get None
                for entity_id in batch:
                    entity_to_value[entity_id] = None

        return entity_to_value

    def _extract_property_value(self, entity_data: dict, property_id: str) -> Any:
        """Extract a property value from Wikidata entity data."""
        claims = entity_data.get("claims", {})
        prop_claims = claims.get(property_id, [])

        if not prop_claims:
            return None

        # Get the first (primary) claim
        claim = prop_claims[0]
        mainsnak = claim.get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})

        value_type = datavalue.get("type")
        value = datavalue.get("value")

        if value_type == "time":
            # Return ISO date string
            return value.get("time") if isinstance(value, dict) else None
        elif value_type == "quantity":
            # Return numeric value
            amount = value.get("amount") if isinstance(value, dict) else None
            if amount:
                try:
                    return float(amount.lstrip("+"))
                except ValueError:
                    return None
        elif value_type == "wikibase-entityid":
            # Return entity ID
            return value.get("id") if isinstance(value, dict) else None
        elif value_type == "string":
            return value

        return value
