# Build Pipeline

Interactively build a new wiki analysis pipeline by describing each stage in plain English.
Claude will read the existing base classes, ask the user to describe the input and output at
each stage, generate an implementation, write it to the project, then assemble a ready-to-run
runner script.

---

## How to run this skill

```
/build-pipeline
```

Optional — pass a one-line description of the full pipeline to skip the intro prompt:

```
/build-pipeline Bulbapedia route page → trainer EXP yield per generation
```

---

## What you must do (step-by-step)

### 0. Read the project

Before asking the user anything, read these files in parallel so you have full context:

- `wiki_gator/models.py`
- `wiki_gator/extractors/base.py`
- `wiki_gator/fetchers/base.py`
- `wiki_gator/transforms/base.py`
- `wiki_gator/aggregators/base.py`

Also read one reference implementation per stage for style guidance:

- `wiki_gator/extractors/wikipedia.py`
- `wiki_gator/fetchers/bulbapedia.py`
- `wiki_gator/transforms/exp_yield.py`
- `wiki_gator/aggregators/numeric.py`

### 1. Introduce the pipeline

Tell the user:

> "I'll walk you through 4 pipeline stages: **Extractor → Fetcher → Transform → Aggregator**.
> For each stage I'll show the existing implementations and ask you to describe the input and
> output in plain English. I'll generate any new code you need, then wire everything into a
> runner script."

### 2. For each of the 4 stages — in order

Present a single AskUserQuestion with **two questions** (use multiSelect: false for each):

**Question A — "Reuse or generate?"**

List the existing implementations for that stage as options, plus a "Generate new" option.
Label each with the class name and a one-line description.

**Question B — only if the user chose "Generate new"**

Ask two follow-up questions (can be in one AskUserQuestion call):
- `input_desc` — "Describe the INPUT: where does the data come from and what does it look like?"
- `output_desc` — "Describe the OUTPUT: what should this stage return or compute?"

**Then generate the class:**

Using the base class, the models, the reference implementation, and the user's descriptions,
write a Python class that:
- Subclasses the correct base class
- Implements every `@abstractmethod`
- Includes all imports
- Has a descriptive class name ending in the stage type (e.g. `MtMoonExtractor`,
  `PokeAPIFetcher`, `LevelWeightedTransform`, `MedianAggregator`)

Write the generated file to the appropriate directory:

| Stage | Directory | Suggested filename |
|---|---|---|
| Extractor | `wiki_gator/extractors/` | `generated_<name>.py` |
| Fetcher | `wiki_gator/fetchers/` | `generated_<name>.py` |
| Transform | `wiki_gator/transforms/` | `generated_<name>.py` |
| Aggregator | `wiki_gator/aggregators/` | `generated_<name>.py` |

Show the user the generated code and the saved file path.

### 3. Stage reference — existing implementations

#### Extractor
| Choice | Class | Module |
|---|---|---|
| 1 | `WikipediaListExtractor` | `wiki_gator.extractors.wikipedia` |
| 2 | `BulbapediaListExtractor` | `wiki_gator.extractors.bulbapedia` |

Input to describe: the source page URL structure
Output to describe: how entries are grouped into sections (each entry has `.name`, `.url`,
`.html_content`, `.metadata`)

#### Fetcher
| Choice | Class | Module |
|---|---|---|
| 1 | `WikidataFetcher` | `wiki_gator.fetchers.wikidata` |
| 2 | `BulbapediaFetcher` | `wiki_gator.fetchers.bulbapedia` |

Input to describe: what data is available on each `Entry` object
Output to describe: the raw value stored on `entry.raw_value` (can be any type — a date
string, a list of dicts, a number, raw HTML)

#### Transform
| Choice | Class | Module |
|---|---|---|
| 1 | `DateToAgeTransform` | `wiki_gator.transforms.date_transforms` |
| 2 | `ExpYieldTransform` | `wiki_gator.transforms.exp_yield` |
| 3 | `IdentityTransform` | `wiki_gator.transforms.date_transforms` |

Input to describe: the raw value format
Output to describe: the `float` it should produce (e.g. age in years, total EXP, raw number)

#### Aggregator
| Choice | Class | Module |
|---|---|---|
| 1 | `AverageAggregator` | `wiki_gator.aggregators.numeric` |
| 2 | `SumAggregator` | `wiki_gator.aggregators.numeric` |
| 3 | `MinAggregator` | `wiki_gator.aggregators.numeric` |
| 4 | `MaxAggregator` | `wiki_gator.aggregators.numeric` |

Input to describe: what each float represents in context
Output to describe: how to combine them (mean, sum, min, max, median, …)

### 4. Collect run parameters

After all 4 stages are resolved, ask (one AskUserQuestion with all fields):

- `url` — URL of the page to analyze
- `level` — section heading level (2 = H2, 3 = H3 …)
- `property_id` — property string to pass to the fetcher (e.g. `base_exp`, `P569`)
- `output_file` — output CSV filename (default `output.csv`)
- `value_label` — label for the aggregated-value column in the CSV (e.g. `Total EXP Yield`)
- `runner_name` — filename for the generated runner script (default `run_pipeline.py`)

### 5. Write the runner script

Generate a Python script at `<runner_name>` that:

```python
#!/usr/bin/env python3
"""Generated pipeline runner."""
import sys
from wiki_gator import WikiGator
from wiki_gator.output.csv_writer import CSVWriter
from <extractor_module> import <ExtractorClass>
from <fetcher_module> import <FetcherClass>
from <transform_module> import <TransformClass>
from <aggregator_module> import <AggregatorClass>

extractor  = <ExtractorClass>()   # adjust constructor args as needed
fetcher    = <FetcherClass>()
transform  = <TransformClass>()
aggregator = <AggregatorClass>()

analyzer = WikiGator(
    extractor=extractor,
    fetcher=fetcher,
    transform=transform,
    aggregator=aggregator,
    progress_callback=lambda msg: print(f"  {msg}"),
)

results = analyzer.analyze(
    url="<url>",
    level=<level>,
    property_id="<property_id>",
)

writer = CSVWriter("<output_file>", value_label="<value_label>")
writer.write(results)

print(f"\nResults written to: <output_file>")
for r in results:
    val = f"{r.aggregated_value:.2f}" if r.aggregated_value is not None else "N/A"
    print(f"  {r.section_name}: {val}  ({r.count} entries, {r.skipped_count} skipped)")
```

Tell the user the runner was saved and how to run it:

```
python <runner_name>
```

---

## Notes

- If the user picks an existing implementation, record its class name and module — no file
  generation needed for that stage.
- If a generated class needs constructor arguments (e.g. `generation_filter`), add a comment
  in the runner: `# TODO: set constructor args`.
- `CSVWriter` accepts a `value_label` kwarg (added in this session) — always pass it.
- The `WikiGator` orchestrator in `wiki_gator/analyzer.py` handles the full
  Extractor → Fetcher → Transform → Aggregator wiring; the runner just instantiates it.
