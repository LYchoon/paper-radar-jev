# Paper Radar

[English](README.md) | [繁體中文](README.zh-TW.md)

A configurable Python CLI that fetches recent arXiv papers, scores their relevance with TypeSafe AI using P(True), and generates daily Markdown and JSON rankings.

## Installation and usage

Requires Python 3.11+, Git, GitHub CLI (`gh`), [uv](https://docs.astral.sh/uv/getting-started/installation/), and your own TypeSafe API key.

### 1. Clone and install

Clone the project with GitHub CLI (`gh`). If you already have the project, run `uv sync` from its root directory.

```sh
gh repo clone LYchoon/paper-radar-jev
cd paper-radar-jev
uv sync
```

`uv sync` creates `.venv` and installs dependencies using `pyproject.toml` and `uv.lock`. It creates or updates the lockfile when necessary. Maintainers should commit `uv.lock` for reproducible dependency versions.

### 2. Create local configuration files

Windows PowerShell:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
if (-not (Test-Path config/config.json)) {
    Copy-Item config/config.example.json config/config.json
}
```

macOS / Linux (Bash or Zsh):

```sh
[ -e .env ] || cp .env.example .env
[ -e config/config.json ] || cp config/config.example.json config/config.json
```

These commands preserve existing local files. Edit `.env` in the project root:

```dotenv
TYPESAFE_API_KEY=your_actual_api_key
```

Put your real key in `.env`, never in `.env.example`. Edit `config/config.json` to set your research interests. The default profile focuses on Computer Vision / Generative Models.

For an initial smoke test, set `sources.arxiv.max_results` to 3 before increasing the count.

### 3. Validate and run

```sh
uv run paper-radar --config config/config.json --check-config
uv run paper-radar --config config/config.json
```

`--check-config` validates the JSON configuration only; it does not validate your key or network access. A normal run fetches arXiv papers and sends your research profile, paper titles, abstracts, and categories to TypeSafe for evaluation.

The original entry point is also supported:

```sh
uv run python main.py --config config/config.json
```

Reports are written to `daily/md/YYYY-MM-DD.md` and `daily/json/YYYY-MM-DD.json`. Historical results and processed IDs are stored in `data/`.

### Environment files and precedence

The application uses [python-dotenv](https://bbc2.github.io/python-dotenv/) to load `.env` from the project root. With a custom configuration file, its location follows the storage base directory described below; unrelated parent directories are not searched.

Existing environment variables take precedence over `.env`. To use the file instead of a key previously set in your current shell, clear the variable first.

PowerShell:

```powershell
Remove-Item Env:TYPESAFE_API_KEY -ErrorAction SilentlyContinue
```

Bash / Zsh:

```sh
unset TYPESAFE_API_KEY
```

Optionally set `TYPESAFE_DEFAULT_MODEL` in `.env`; otherwise the SDK default is used. Restart the command after editing `.env`.

`.env.example` and `config/config.example.json` are public templates. The real `.env`, personal `config/config.json`, generated data, and reports are excluded by `.gitignore`.

## Configuration

The example targets Computer Vision / Generative Models. All research-specific descriptions live in JSON; Python does not hard-code a research domain.

| Setting | Purpose |
|---|---|
| `profile` | Report profile name and description |
| `research.summary` | Main research direction |
| `research.interests` | Core topics |
| `research.related_topics` | Related topics |
| `research.negative_topics` | Topics to exclude |
| `research.evaluation_guidance` | Evaluation criteria |
| `sources.arxiv.categories` | Defaults to cs.CV, cs.LG, cs.AI, cs.GR |
| `sources.arxiv.max_results` | Latest N papers; default 100 |
| `evaluation.relevance_threshold` | Inclusive relevance threshold; default 0.5 |
| `evaluation.high_priority_threshold` | High-priority threshold; default 0.8 |
| `evaluation.dimensions` | Enable and define additional evaluation questions |
| `output.include_irrelevant` | Include below-threshold papers in Markdown only |
| `output.max_papers_in_report` | Maximum papers in Markdown only; default 50 |
| `output.markdown / json` | Output formats; at least one must be enabled |

Reports sort by decreasing relevance score by default; `output.sort_order = "ascending"` is also supported. arXiv `sort_by` accepts `submitted_date`, `last_updated_date`, or `relevance`. Its `sort_order` accepts `ascending` or `descending`.

When dimensions are enabled, the overall and dimension questions are combined into one request per paper. The name `relevant` is reserved for the overall question. Out-of-range values, unknown fields, empty research summaries, empty category lists, and inconsistent thresholds are rejected.

### Paths and switching research profiles

Relative `storage` paths are resolved against the configuration file's directory. If that directory is named `config`, its parent is used instead. The standard layout keeps `config/`, `data/`, and `daily/` alongside each other, independent of the shell's working directory. Absolute paths are also supported.

After changing `profile`, `research`, or `evaluation`, use separate storage paths, for example:

```json
{
  "seen_file": "data/robotics/seen.json",
  "database_file": "data/robotics/papers.jsonl",
  "daily_output_dir": "daily/robotics"
}
```

Alternatively, archive the old dataset and start fresh. The application rejects reuse of a database with a different research profile to avoid incorrectly skipping papers. Changing only `output` does not require reevaluation.

## Output and recovery

- Generates `daily/md/YYYY-MM-DD.md` and `daily/json/YYYY-MM-DD.json`.
- `data/seen.json` tracks successfully processed IDs. `data/papers.jsonl` stores all successful evaluations, including low-scoring papers.
- Versions such as arXiv v1 and v2 are treated as the same paper. Legacy IDs are supported.
- No fixed 24-hour window is used. The latest N papers are compared against processed IDs. If more than N papers accumulate between runs, older papers can still be missed; increase N to catch up.
- Empty abstracts, failed API calls, missing answers, and invalid probabilities are not marked as seen. Evaluation continues for other papers.
- TypeSafe uses SDK retries: up to 3 after the initial attempt, with a 1-second initial backoff and a 4-second cap. The SDK may apply jitter or honor Retry-After. HTTP timeout is 30 seconds and the retry budget is 60 seconds.
- arXiv uses package pagination and up to 3 retries, with a 3-second request interval.
- Each successful evaluation is saved to JSONL before reporting. The seen file is updated after reports are written. Subsequent runs recover persisted evaluations without scoring those papers again.
- Repeated runs on the same day preserve and combine results. A run with no new papers does not erase the existing report.
- Reports for every recorded date are rebuilt from the database to recover interrupted writes. Dates use the local execution date.
- Statistics cover all successful evaluations for the day. Markdown applies relevance filtering and the display limit; JSON always contains every successful evaluation, including low scores, complete metadata, and all dimension scores, without display rounding. In each format, `statistics.shown` counts its included papers. Failed API requests have no computed result and remain retryable; their count appears in CLI logs and the exit code.
- Each JSONL record contains paper fields, `date`, and `profile_key`. The MVP adds records through atomic file rewrites to avoid partial lines; larger datasets could migrate to SQLite.
- Seen files, the database, and reports use temporary files followed by atomic replacement. File locks prevent concurrent writes to shared storage. Lock files may remain on disk; their OS locks are released when the process exits.
- Corrupt data, or seen IDs missing from the database, stop the run while preserving the original files. Restore a backup or archive the dataset before starting fresh.
- Disabling arXiv skips fetching new papers but still allows existing reports to be rebuilt.

Existing reports in the old `daily/` layout are left in place. On the next successful run, historical reports are rebuilt from `data/papers.jsonl` into `daily/md/` and `daily/json/`, without reevaluating persisted papers.

## Tests

Run from the project root:

```powershell
uv sync
uv run pytest -q
```

Tests cover configuration validation, ID normalization, metadata, probability boundaries, dimensions, SDK retry settings, seen/JSONL persistence, report sorting and filtering, individual failures, storage failures, recovery across dates, and profile changes. Data sources and evaluation requests use test doubles; tests do not call live arXiv or TypeSafe APIs.

For a live smoke test, set `max_results` to 3, optionally disable dimensions, and configure your key. Check reports and deduplication before increasing the count.

| Exit code | Meaning |
|---|---|
| 0 | Successful run or configuration check |
| 1 | Configuration, fetching, storage, or another overall failure |
| 2 | Reports generated, but some evaluations failed; rerun to retry |
| 130 | Interrupted by the user |

## Project structure

```text
paper-radar-jev/
├── README.md
├── README.zh-TW.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── main.py
├── config/
│   ├── config.example.json
│   └── config.json
├── src/paper_radar/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── fetch.py
│   ├── evaluator.py
│   ├── storage.py
│   ├── report.py
│   └── pipeline.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_fetch.py
│   ├── test_evaluator.py
│   ├── test_storage.py
│   ├── test_report.py
│   ├── test_pipeline.py
│   └── test_cli.py
├── data/.gitkeep
└── daily/.gitkeep
```

Create `.env` and `config/config.json` from the examples. `.venv/` and runtime data are created during installation or execution. Keep `uv.lock` in version control; personal configuration, data, reports, and `.env` are ignored. This version does not schedule runs or automatically commit or push changes.

## Official references

- [TypeSafe Python SDK](https://docs.typesafe.ai/sdk/python)
- [Synchronous client parameters](https://docs.typesafe.ai/sdk/python/api/clients/sync)
- [RetryPolicy](https://docs.typesafe.ai/sdk/python/api/retries)
- [arxiv package documentation](https://lukasschwab.me/arxiv.py/arxiv.html)
