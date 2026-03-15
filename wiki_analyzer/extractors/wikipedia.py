"""Wikipedia list extractor implementation."""

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from ..models import Entry, EntryList, Section
from .base import ListExtractor


class WikipediaListExtractor(ListExtractor):
    """Extracts entries from Wikipedia 'List of' articles.

    Parses the HTML structure of Wikipedia pages to identify
    sections (by heading level) and extract links to individual
    entries within each section.
    """

    def __init__(self, session: requests.Session | None = None):
        """Initialize the extractor.

        Args:
            session: Optional requests session for connection pooling.
        """
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": "WikiAnalyzer/1.0 (Educational/Research Tool)"}
        )

    def extract(self, url: str, level: int) -> list[Section]:
        """Extract sections and entries from a Wikipedia list page.

        Args:
            url: The Wikipedia URL (e.g., https://en.wikipedia.org/wiki/List_of_...).
            level: Heading level for section grouping (2=H2, 3=H3, etc.).

        Returns:
            List of Section objects with entries populated.
        """
        response = self.session.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Wikipedia content is inside mw-content-text > mw-parser-output
        content = soup.find("div", {"class": "mw-parser-output"})
        if not content:
            # Fallback to older structure
            content = soup.find("div", {"id": "mw-content-text"})

        if not content:
            return []

        base_url = self._get_base_url(url)
        sections = self._parse_sections(content, level, base_url)

        return sections

    def _get_base_url(self, url: str) -> str:
        """Extract base URL for resolving relative links."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _parse_sections(self, content: Tag, level: int, base_url: str) -> list[Section]:
        """Parse content into sections based on heading level."""
        sections: list[Section] = []
        heading_tag = f"h{level}"

        # Find all headings at the specified level
        headings = content.find_all(heading_tag)

        for heading in headings:
            section_name = self._get_heading_text(heading)

            # Skip certain meta-sections
            if self._should_skip_section(section_name):
                continue

            # Collect content between this heading and the next same-level heading
            entries = self._extract_entries_after_heading(
                heading, heading_tag, base_url
            )

            if entries:
                section = Section(
                    name=section_name, level=level, lists=[EntryList(entries=entries)]
                )
                sections.append(section)

        return sections

    def _get_heading_text(self, heading: Tag) -> str:
        """Extract clean text from a heading element."""
        # Try multiple selectors for different Wikipedia skins

        # Vector 2022 skin uses <span class="mw-headline">
        headline = heading.find(class_="mw-headline")
        if headline:
            return headline.get_text(strip=True)

        # Newer structure might use <span id="...">
        span = heading.find("span", id=True)
        if span:
            return span.get_text(strip=True)

        # Fallback: get all text but remove edit section links
        text = heading.get_text(strip=True)
        # Remove common suffixes like "[edit]"
        text = re.sub(r"\[edit\]$", "", text).strip()
        return text

    def _should_skip_section(self, name: str) -> bool:
        """Check if section should be skipped (meta-sections)."""
        skip_patterns = [
            "see also",
            "references",
            "external links",
            "notes",
            "further reading",
            "bibliography",
            "sources",
        ]
        return name.lower() in skip_patterns

    def _extract_entries_after_heading(
        self, heading: Tag, heading_tag: str, base_url: str
    ) -> list[Entry]:
        """Extract all entry links between this heading and the next."""
        entries: list[Entry] = []
        seen_urls: set[str] = set()

        # Modern Wikipedia wraps headings in <div class="mw-heading">
        # So we need to iterate siblings of the wrapper, not the heading itself
        start_element = heading
        if heading.parent and heading.parent.get("class"):
            parent_classes = heading.parent.get("class", [])
            if "mw-heading" in parent_classes:
                start_element = heading.parent

        # Iterate through siblings until we hit another heading of same level
        heading_level = int(heading_tag[1])

        for sibling in start_element.find_next_siblings():
            # Check if this is a heading wrapper (new Wikipedia structure)
            if sibling.name == "div" and sibling.get("class"):
                classes = sibling.get("class", [])
                if "mw-heading" in classes:
                    # Extract level from class like "mw-heading2"
                    for cls in classes:
                        if cls.startswith("mw-heading") and cls != "mw-heading":
                            try:
                                sibling_level = int(cls.replace("mw-heading", ""))
                                if sibling_level <= heading_level:
                                    break
                            except ValueError:
                                pass
                    else:
                        continue
                    break

            # Stop at next heading of same or higher level (old structure)
            if sibling.name and sibling.name.startswith("h"):
                sibling_level = (
                    int(sibling.name[1]) if sibling.name[1].isdigit() else 99
                )
                if sibling_level <= heading_level:
                    break

            # Extract links from lists (ul, ol) and tables
            links = self._extract_links_from_element(sibling, base_url)

            for url, name in links:
                if url not in seen_urls:
                    seen_urls.add(url)
                    entries.append(Entry(name=name, url=url))

        return entries

    def _extract_links_from_element(
        self, element: Tag, base_url: str
    ) -> list[tuple[str, str]]:
        """Extract Wikipedia article links from an element."""
        links: list[tuple[str, str]] = []

        if not hasattr(element, "find_all"):
            return links

        for a_tag in element.find_all("a", href=True):
            href = a_tag["href"]

            # Only include links to Wikipedia articles
            if not self._is_wiki_article_link(href):
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, href)
            name = a_tag.get_text(strip=True)

            if name:  # Only include links with visible text
                links.append((full_url, name))

        return links

    def _is_wiki_article_link(self, href: str) -> bool:
        """Check if a link points to a Wikipedia article."""
        # Must start with /wiki/
        if not href.startswith("/wiki/"):
            return False

        # Exclude special pages, files, categories, etc.
        excluded_prefixes = [
            "/wiki/File:",
            "/wiki/Category:",
            "/wiki/Template:",
            "/wiki/Wikipedia:",
            "/wiki/Help:",
            "/wiki/Portal:",
            "/wiki/Special:",
            "/wiki/Talk:",
            "/wiki/User:",
            "/wiki/Module:",
            "/wiki/MediaWiki:",
        ]

        for prefix in excluded_prefixes:
            if href.startswith(prefix):
                return False

        # Exclude fragment-only links and query strings
        if "#" in href.split("/")[-1] and href.index("#") < len(href) - 1:
            # Has a fragment, but might still be a valid article link
            pass

        return True
