#!/usr/bin/env python3
"""Interactive pipeline builder using Claude API.

Walks through each pipeline stage (Extractor → Fetcher → Transform → Aggregator),
prompts the user for natural language descriptions of the input and output at each
stage, then uses Claude to generate a Python class implementing the matching base
class.  After all four stages are configured, it writes a ready-to-run runner script.

Usage:
    python build_pipeline.py
"""

import os
import re
import sys
import textwrap
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
WIKI_DIR = BASE_DIR / "wiki_analyzer"
MODELS_FILE = WIKI_DIR / "models.py"

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------
STAGES = [
    {
        "id": "extractor",
        "name": "Extractor",
        "num": 1,
        "summary": (
            "Fetches a page and groups entries into named sections.\n"
            "  Input:  URL (str), heading level (int)\n"
            "  Output: List[Section]  — each Section has a name and Entry objects\n"
            "          Entry has: .name, .url, .html_content, .metadata"
        ),
        "base_class": "ListExtractor",
        "base_file": WIKI_DIR / "extractors" / "base.py",
        "example_file": WIKI_DIR / "extractors" / "wikipedia.py",
        "output_dir": WIKI_DIR / "extractors",
        "existing": {
            "1": ("WikipediaListExtractor", "wiki_analyzer.extractors.wikipedia",
                  "Parses Wikipedia 'List of' pages"),
            "2": ("BulbapediaListExtractor", "wiki_analyzer.extractors.bulbapedia",
                  "Parses Bulbapedia route/location pages (trainer parties)"),
        },
        "input_q": "Describe the DATA SOURCE — what page/URL are you scraping and how is it structured?",
        "output_q": "Describe the ENTRIES — how are they grouped into sections, and what data does each entry carry?",
    },
    {
        "id": "fetcher",
        "name": "Fetcher",
        "num": 2,
        "summary": (
            "Given Entry objects, fetches the raw attribute value for each.\n"
            "  Input:  List[Entry], property_id (str)\n"
            "  Output: dict[entry_key → raw_value]  (also sets entry.raw_value directly)"
        ),
        "base_class": "DataFetcher",
        "base_file": WIKI_DIR / "fetchers" / "base.py",
        "example_file": WIKI_DIR / "fetchers" / "bulbapedia.py",
        "output_dir": WIKI_DIR / "fetchers",
        "existing": {
            "1": ("WikidataFetcher", "wiki_analyzer.fetchers.wikidata",
                  "Resolves Wikipedia URLs → Wikidata entities → property values"),
            "2": ("BulbapediaFetcher", "wiki_analyzer.fetchers.bulbapedia",
                  "Parses trainer HTML and fetches base EXP from PokeAPI"),
        },
        "input_q": "Describe the ENTRY DATA available (e.g. .url to a wiki article, .html_content with raw HTML, .metadata dict).",
        "output_q": "Describe the RAW VALUE to return — what data should be fetched or extracted for each entry?",
    },
    {
        "id": "transform",
        "name": "Transform",
        "num": 3,
        "summary": (
            "Converts a single raw value into a float for aggregation.\n"
            "  Input:  raw_value (Any)\n"
            "  Output: float | None"
        ),
        "base_class": "Transform",
        "base_file": WIKI_DIR / "transforms" / "base.py",
        "example_file": WIKI_DIR / "transforms" / "exp_yield.py",
        "output_dir": WIKI_DIR / "transforms",
        "existing": {
            "1": ("DateToAgeTransform", "wiki_analyzer.transforms.date_transforms",
                  "Wikidata date string → age in years"),
            "2": ("ExpYieldTransform", "wiki_analyzer.transforms.exp_yield",
                  "List of Pokémon dicts → total EXP yield using (base_exp × level) / 7"),
            "3": ("IdentityTransform", "wiki_analyzer.transforms.date_transforms",
                  "Numeric value → float (no-op)"),
        },
        "input_q": "Describe the RAW VALUE coming in — its type and structure (e.g. a date string, a list of dicts, a number).",
        "output_q": "Describe the NUMERIC VALUE to produce — what calculation turns the raw value into a float?",
    },
    {
        "id": "aggregator",
        "name": "Aggregator",
        "num": 4,
        "summary": (
            "Combines a list of floats (one per entry in a section) into a summary value.\n"
            "  Input:  List[float]\n"
            "  Output: float | None"
        ),
        "base_class": "Aggregator",
        "base_file": WIKI_DIR / "aggregators" / "base.py",
        "example_file": WIKI_DIR / "aggregators" / "numeric.py",
        "output_dir": WIKI_DIR / "aggregators",
        "existing": {
            "1": ("AverageAggregator", "wiki_analyzer.aggregators.numeric", "Arithmetic mean"),
            "2": ("SumAggregator", "wiki_analyzer.aggregators.numeric", "Sum"),
            "3": ("MinAggregator", "wiki_analyzer.aggregators.numeric", "Minimum"),
            "4": ("MaxAggregator", "wiki_analyzer.aggregators.numeric", "Maximum"),
        },
        "input_q": "Describe the LIST OF VALUES — what does each float represent?",
        "output_q": "Describe the AGGREGATION — how should the floats be combined (average, sum, max, …)?",
    },
]

# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
BAR   = "─" * 62
THICK = "═" * 62


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"\n{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return value or default


def _ask_multiline(prompt: str) -> str:
    """Read multi-line input; empty line after content finishes input."""
    print(f"\n  {prompt}")
    print("  (enter your description; press Enter on an empty line to finish)")
    lines: list[str] = []
    try:
        while True:
            line = input("  > ")
            if not line and lines:
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        print()
    return "\n".join(lines).strip()


def _extract_class_name(code: str, base_class: str) -> str | None:
    match = re.search(rf"class\s+(\w+)\s*\(\s*{base_class}\s*\)", code)
    if match:
        return match.group(1)
    match = re.search(r"class\s+(\w+)\s*\(", code)
    return match.group(1) if match else None


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:python)?\s*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


# ---------------------------------------------------------------------------
# Claude code generation
# ---------------------------------------------------------------------------
def generate_implementation(
    client: anthropic.Anthropic,
    stage: dict,
    input_desc: str,
    output_desc: str,
) -> str:
    models_code   = _read(MODELS_FILE)
    base_code     = _read(stage["base_file"])
    example_code  = _read(stage["example_file"])

    system = textwrap.dedent("""\
        You are a Python code generator for a modular wiki-scraping analysis framework.
        The framework has four pipeline stages: Extractor → Fetcher → Transform → Aggregator.

        Rules:
        - Return ONLY valid Python source — no prose, no markdown fences.
        - Implement every abstract method from the base class.
        - Include all necessary imports at the top of the file.
        - Use `requests` and `beautifulsoup4` (bs4) for any web scraping.
        - Write clear docstrings on the class and each method.
        - Choose a descriptive class name ending with the stage type
          (e.g. MtMoonExtractor, PokeAPIFetcher, LevelScoreTransform, MedianAggregator).
    """)

    user = textwrap.dedent(f"""\
        ## Framework data models
        ```python
        {models_code}
        ```

        ## Base class to implement
        ```python
        {base_code}
        ```

        ## Reference implementation (style only — do not copy logic verbatim)
        ```python
        {example_code}
        ```

        ## Your task
        Generate a Python class that subclasses `{stage["base_class"]}`.

        Input description (what this stage receives / where data comes from):
        {input_desc}

        Output description (what this stage must return / compute):
        {output_desc}

        Return only the Python source file.
    """)

    print("\n  Generating with Claude", end="", flush=True)
    chunks: list[str] = []
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)
            print(".", end="", flush=True)
    print(" done\n")

    return _strip_fences("".join(chunks))


# ---------------------------------------------------------------------------
# Per-stage interactive flow
# ---------------------------------------------------------------------------
def run_stage(client: anthropic.Anthropic, stage: dict) -> dict:
    print(f"\n{THICK}")
    print(f"  Stage {stage['num']}/4 — {stage['name'].upper()}")
    print(THICK)
    print(f"\n{stage['summary']}\n")

    print(f"  {BAR}")
    print("  Existing implementations:")
    for key, (cls, mod, desc) in stage["existing"].items():
        print(f"    [{key}] {cls}")
        print(f"        {desc}")
    print("    [g] Generate a new implementation with Claude")
    print(f"  {BAR}")

    choice = _ask("  Your choice", default="g").strip().lower()

    if choice in stage["existing"]:
        cls_name, mod_path, _ = stage["existing"][choice]
        print(f"\n  ✓ Using {cls_name}  ({mod_path})")
        return {
            "class_name": cls_name,
            "module_path": mod_path,
            "constructor_hint": f"{cls_name}()",
            "generated": False,
        }

    # --- Generate new ---
    input_desc  = _ask_multiline(stage["input_q"])
    output_desc = _ask_multiline(stage["output_q"])

    code = generate_implementation(client, stage, input_desc, output_desc)

    # Preview
    print(f"  {BAR}\n  Generated code:\n")
    for line in code.splitlines():
        print(f"    {line}")
    print(f"\n  {BAR}")

    cls_name = _extract_class_name(code, stage["base_class"]) or f"Generated{stage['name']}"
    file_name = f"generated_{cls_name.lower()}.py"
    out_path  = stage["output_dir"] / file_name

    action = _ask(
        f"  Save to {out_path.relative_to(BASE_DIR)}? [y / n / edit]",
        default="y"
    ).lower()

    if action == "n":
        print("  ⚠  Skipped — add the class to the project manually.")
    elif action == "edit":
        out_path.write_text(code, encoding="utf-8")
        editor = os.environ.get("EDITOR", "notepad" if sys.platform == "win32" else "nano")
        os.system(f'{editor} "{out_path}"')
        code = out_path.read_text(encoding="utf-8")
        cls_name = _extract_class_name(code, stage["base_class"]) or cls_name
        print(f"  ✓ Saved {out_path.relative_to(BASE_DIR)}")
    else:
        out_path.write_text(code, encoding="utf-8")
        print(f"  ✓ Saved {out_path.relative_to(BASE_DIR)}")

    module_rel = (
        str(out_path.relative_to(BASE_DIR).with_suffix(""))
        .replace(os.sep, ".")
        .replace("/", ".")
    )
    return {
        "class_name": cls_name,
        "module_path": module_rel,
        "constructor_hint": f"{cls_name}()",
        "generated": True,
    }


# ---------------------------------------------------------------------------
# Runner script generation
# ---------------------------------------------------------------------------
RUNNER_TEMPLATE = '''\
#!/usr/bin/env python3
"""Generated pipeline runner — created by build_pipeline.py."""

import sys
from wiki_analyzer import WikiAnalyzer
from wiki_analyzer.output.csv_writer import CSVWriter
from {extractor_module} import {extractor_class}
from {fetcher_module} import {fetcher_class}
from {transform_module} import {transform_class}
from {aggregator_module} import {aggregator_class}

URL         = "{url}"
LEVEL       = {level}
PROPERTY_ID = "{property_id}"
OUTPUT_FILE = "{output_file}"
VALUE_LABEL = "{value_label}"

# TODO: adjust constructor arguments as needed
extractor  = {extractor_constructor}
fetcher    = {fetcher_constructor}
transform  = {transform_constructor}
aggregator = {aggregator_constructor}

analyzer = WikiAnalyzer(
    extractor=extractor,
    fetcher=fetcher,
    transform=transform,
    aggregator=aggregator,
    progress_callback=lambda msg: print(f"  {{msg}}"),
)

results = analyzer.analyze(
    url=URL,
    level=LEVEL,
    property_id=PROPERTY_ID,
)

writer = CSVWriter(OUTPUT_FILE, value_label=VALUE_LABEL)
writer.write(results)
print(f"\\nResults written to: {{OUTPUT_FILE}}")
for r in results:
    val = f"{{r.aggregated_value:.2f}}" if r.aggregated_value is not None else "N/A"
    print(f"  {{r.section_name}}: {{val}}  ({{r.count}} entries, {{r.skipped_count}} skipped)")
'''


def generate_runner(stage_results: list[dict]) -> None:
    extractor, fetcher, transform, aggregator = stage_results

    print(f"\n{THICK}")
    print("  Pipeline Summary")
    print(THICK)
    for label, info in zip(
        ["Extractor ", "Fetcher   ", "Transform ", "Aggregator"], stage_results
    ):
        print(f"  {label}  {info['class_name']}  ({info['module_path']})")

    print(f"\n{BAR}\n  Configure the run:\n")
    url          = _ask("  URL to analyze")
    level        = int(_ask("  Section heading level", default="2"))
    property_id  = _ask("  Property ID to pass to fetcher", default="base_exp")
    output_file  = _ask("  Output CSV filename", default="output.csv")
    value_label  = _ask("  CSV value-column label", default="Aggregated Value")
    runner_name  = _ask("  Runner script filename", default="run_pipeline.py")

    code = RUNNER_TEMPLATE.format(
        extractor_module=extractor["module_path"],
        extractor_class=extractor["class_name"],
        fetcher_module=fetcher["module_path"],
        fetcher_class=fetcher["class_name"],
        transform_module=transform["module_path"],
        transform_class=transform["class_name"],
        aggregator_module=aggregator["module_path"],
        aggregator_class=aggregator["class_name"],
        extractor_constructor=extractor["constructor_hint"],
        fetcher_constructor=fetcher["constructor_hint"],
        transform_constructor=transform["constructor_hint"],
        aggregator_constructor=aggregator["constructor_hint"],
        url=url,
        level=level,
        property_id=property_id,
        output_file=output_file,
        value_label=value_label,
    )

    runner_path = BASE_DIR / runner_name
    runner_path.write_text(code, encoding="utf-8")
    print(f"\n  ✓ Runner saved to {runner_name}")
    print(f"\n  Run it with:\n    python {runner_name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY environment variable is not set.\n"
            "Export it before running:  export ANTHROPIC_API_KEY=sk-...",
            file=sys.stderr,
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"\n{THICK}")
    print("  Wiki Pipeline Builder  (powered by Claude)")
    print(THICK)
    print(
        "\n  This tool builds a 4-stage wiki analysis pipeline:\n"
        "\n    1. Extractor  — scrapes a page and groups entries into sections"
        "\n    2. Fetcher    — fetches data for each entry"
        "\n    3. Transform  — converts raw data to a float"
        "\n    4. Aggregator — combines floats per section into a single value"
        "\n\n  For each stage you can pick an existing implementation or describe"
        "\n  the input/output in plain English and Claude will generate the code."
    )

    stage_results: list[dict] = []
    for stage in STAGES:
        result = run_stage(client, stage)
        stage_results.append(result)

    generate_runner(stage_results)
    print(f"\n{THICK}\n  Done!\n{THICK}\n")


if __name__ == "__main__":
    main()
