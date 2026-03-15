# WikiGator

A command-line tool that scrapes Wikipedia "List of" pages, looks up each person's birth and death dates via Wikidata, and computes the **average age** per section (grouped by heading level).

---

## Requirements

- Python 3.10+
- `requests`
- `beautifulsoup4`

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python main.py <WIKIPEDIA_URL> [OPTIONS]
```

### Positional argument

| Argument | Description |
|---|---|
| `url` | Full URL of the Wikipedia "List of" page to analyze |

### Options

| Flag | Default | Description |
|---|---|---|
| `--level`, `-l` | `2` | Heading level for section grouping (`2` = H2, `3` = H3, etc.) |
| `--output`, `-o` | `output.csv` | Path for the output CSV file |
| `--property`, `-p` | `P569` | Wikidata property ID to fetch (default: birth date) |
| `--death-property` | `P570` | Wikidata property ID for death date |
| `--no-death-date` | — | Ignore death dates; compute age using today's date only |
| `--debug` | — | Also write a per-entry debug CSV alongside the summary CSV |
| `--quiet`, `-q` | — | Suppress all progress output |

---

## Examples

### Average age of US playwrights (grouped by first letter)

```bash
python main.py "https://en.wikipedia.org/wiki/List_of_playwrights_from_the_United_States" --level 2 --output playwrights.csv
```

### Average age using only current date (ignore death dates)

```bash
python main.py "https://en.wikipedia.org/wiki/List_of_playwrights_from_the_United_States" --no-death-date
```

### Include per-entry debug output

```bash
python main.py "https://en.wikipedia.org/wiki/List_of_playwrights_from_the_United_States" --debug
```

---

## Output

The tool writes a CSV file with one row per section:

| Column | Description |
|---|---|
| `section` | Section heading (e.g., letter of the alphabet) |
| `average_age` | Average age of playwrights in that section |
| `count` | Number of entries with valid age data |
| `skipped` | Number of entries where age could not be determined |

When `--debug` is used, an additional `*.debug.csv` file is written containing a row per individual entry with their raw and computed values.

---

## How it works

1. **Extract** — Parses the Wikipedia page and groups hyperlinked names by section heading.
2. **Fetch** — Looks up each person's Wikidata entry (in batches) to retrieve birth date (`P569`) and death date (`P570`).
3. **Transform** — Converts dates to ages. Living persons use today's date; deceased persons use their date of death.
4. **Aggregate** — Computes the average age per section.
5. **Output** — Writes results to a CSV file.

---

## Common Wikidata properties

| Property | Description |
|---|---|
| `P569` | Date of birth |
| `P570` | Date of death |
| `P2048` | Height |
| `P2067` | Mass |
