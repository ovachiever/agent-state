#!/usr/bin/env python3
"""Deterministic fixture generator for the toolhunt-deep task.

Emits BOTH trees:
  fixture/   — the ~87-file flowline ETL project the agent sees
  solution/  — only the 11 files that change, derived from the same
               templates by a word-boundary OLD -> NEW rename

Design notes for variant authors:
  * No randomness, no wall-clock: every byte comes from the literal
    templates below, so two runs always produce identical trees (the
    script prints a tree sha256 to prove it).
  * The rename surface is defined once, in CHANGED_FILES. The solution
    overlay is derived mechanically from it, so fixture and solution
    cannot drift apart.
  * Decoy names deliberately contain OLD as a substring with a leading
    or trailing word character (fold_partition_metrics_v1,
    unfold_partition_metrics, ...) so a blind `sed s/OLD/NEW/g` corrupts
    them; verify.py byte-checks the decoy files.
  * To make a variant: change OLD/NEW/CANARY, re-point the canary file,
    or move call sites — then update verify.py's constants to match and
    re-run `solm selftest --tasks toolhunt-deep`.

Usage: python3 generate_fixture.py
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OLD = "fold_partition_metrics"
NEW = "consolidate_partition_metrics"
OLD_WORD = re.compile(r"(?<![A-Za-z0-9_])fold_partition_metrics(?![A-Za-z0-9_])")

# ---------------------------------------------------------------------------
# Boilerplate builders (readers / cleaning / enrich / sinks are variations
# stamped out from these templates).
# ---------------------------------------------------------------------------


def reader_module(fmt: str, func: str, ext: str, delim: str) -> str:
    return f'''"""Read {fmt} inputs into row dicts."""

from flowline.core.errors import ReaderError


def {func}(path, limit=None):
    """Load rows from a {fmt} file at *path*.

    Returns a list of dicts, one per record. *limit* caps the number of
    rows read; ``None`` reads everything.
    """
    text = _slurp(path)
    rows = [_parse_line(line) for line in text.splitlines() if line.strip()]
    return rows[:limit] if limit is not None else rows


def _slurp(path):
    if not str(path).endswith("{ext}"):
        raise ReaderError(f"expected a {ext} file, got {{path!r}}")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _parse_line(line):
    parts = [part.strip() for part in line.split({delim!r})]
    return {{"raw": line, "fields": parts}}
'''


def cleaning_module(func: str, summary: str, body: str) -> str:
    return f'''"""Cleaning transform: {summary}"""


def {func}(rows):
    """Return a new row list with {summary}"""
{body}
'''


def enrich_module(func: str, summary: str, key: str, expr: str) -> str:
    return f'''"""Enrichment transform: {summary}"""


def {func}(rows):
    """Return new rows with a {key!r} key added ({summary})."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated[{key!r}] = {expr}
        enriched.append(updated)
    return enriched
'''


def sink_module(fmt: str, func: str, line_expr: str) -> str:
    return f'''"""Sink: serialize processed rows as {fmt}."""

from flowline.core.errors import SinkError


def {func}(rows, stream):
    """Write *rows* to *stream* as {fmt}; returns the row count."""
    if stream is None:
        raise SinkError("{fmt} sink needs an open stream")
    count = 0
    for row in rows:
        stream.write({line_expr} + "\\n")
        count += 1
    return count
'''


# ---------------------------------------------------------------------------
# The rename surface: every file that references OLD and must change.
# Written into fixture/ as-is; written into solution/ with OLD -> NEW
# applied on word boundaries (decoy names like fold_partition_metrics_v1
# survive the sub untouched, which is exactly the point).
# ---------------------------------------------------------------------------

CHANGED_FILES: dict[str, str] = {}

CHANGED_FILES["flowline/transforms/aggregate/windows.py"] = '''"""Windowed aggregation over partitioned measurements."""


def fold_partition_metrics(rows, precision=2):
    """Collapse (partition, value) pairs into per-partition totals.

    Returns a dict mapping partition name to its rounded total, ordered
    by partition name for stable output.
    """
    # CANARY: umber-lattice
    totals = {}
    for partition, value in rows:
        totals[partition] = totals.get(partition, 0.0) + float(value)
    return {name: round(total, precision) for name, total in sorted(totals.items())}


def windowed_rollup(rows, width=7):
    """Fold *rows*, then chunk the totals into windows of *width* entries."""
    folded = sorted(fold_partition_metrics(rows).items())
    return [dict(folded[i:i + width]) for i in range(0, len(folded), width)]
'''

CHANGED_FILES["flowline/transforms/aggregate/__init__.py"] = '''"""Aggregation transforms."""

from flowline.transforms.aggregate.grouping import fold_metric_partitions
from flowline.transforms.aggregate.percentiles import percentile_profile
from flowline.transforms.aggregate.stats import fold_partition_series, fold_partition_stats
from flowline.transforms.aggregate.windows import fold_partition_metrics, windowed_rollup

__all__ = [
    "fold_metric_partitions",
    "percentile_profile",
    "fold_partition_series",
    "fold_partition_stats",
    "fold_partition_metrics",
    "windowed_rollup",
]
'''

CHANGED_FILES["flowline/transforms/__init__.py"] = '''"""Transform layers: cleaning -> enrich -> aggregate."""

from flowline.transforms.aggregate import fold_partition_metrics, windowed_rollup
from flowline.transforms.cleaning import dedupe, drop_nulls, trim_whitespace

__all__ = [
    "fold_partition_metrics",
    "windowed_rollup",
    "dedupe",
    "drop_nulls",
    "trim_whitespace",
]
'''

CHANGED_FILES["flowline/cli.py"] = '''"""Command-line entry point: summarize a measurements file."""

import argparse

from flowline.transforms import fold_partition_metrics


def summarize(rows):
    """One-line human summary of folded partition totals."""
    totals = fold_partition_metrics(rows)
    grand = round(sum(totals.values()), 2)
    return f"{len(totals)} partitions, grand total {grand:.2f}"


def load_measurements(path):
    """Parse `partition,value` lines into measurement pairs."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            partition, _, value = line.partition(",")
            rows.append((partition.strip(), float(value)))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(prog="flowline")
    parser.add_argument("measurements", help="csv of partition,value lines")
    args = parser.parse_args(argv)
    print(summarize(load_measurements(args.measurements)))


if __name__ == "__main__":
    main()
'''

CHANGED_FILES["flowline/reporting/__init__.py"] = '''"""Reporting helpers built on the aggregate transforms.

Example::

    >>> from flowline.transforms.aggregate import fold_partition_metrics
    >>> fold_partition_metrics([("us-east", 1.0), ("us-east", 2.0)])
    {'us-east': 3.0}
"""
'''

CHANGED_FILES["flowline/reporting/weekly.py"] = '''"""Weekly digest lines for the ops channel."""

from flowline.transforms.aggregate import fold_partition_metrics


def partition_digest(rows):
    """Render folded totals as `name=total` joined with pipes."""
    totals = fold_partition_metrics(rows)
    return " | ".join(f"{name}={total:.2f}" for name, total in totals.items())
'''

CHANGED_FILES["flowline/scheduling/jobs.py"] = '''"""Nightly and weekly job bodies invoked by the scheduler."""

from flowline.scheduling.retry import with_retry
from flowline.transforms.aggregate.windows import fold_partition_metrics


def nightly_rollup_job(rows):
    """Fold the day's measurements and emit scheduler metadata."""
    totals = fold_partition_metrics(rows)
    return {"partitions": len(totals), "total": round(sum(totals.values()), 2)}


def weekly_report_job(rows):
    """Nightly rollup plus a retry-wrapped delivery of the payload."""
    payload = nightly_rollup_job(rows)
    return with_retry(lambda: payload, attempts=3)
'''

CHANGED_FILES["flowline/sinks/digest.py"] = '''"""Digest sink: folded totals as `partition,total` lines."""

from flowline.transforms.aggregate import fold_partition_metrics


def write_digest(rows, stream):
    """Fold *rows* and write one `partition,total` line per partition."""
    totals = fold_partition_metrics(rows)
    for name, total in totals.items():
        stream.write(f"{name},{total:.2f}\\n")
    return len(totals)
'''

CHANGED_FILES["flowline/core/pipeline.py"] = '''"""Pipeline orchestration: resolve steps, run them, summarize."""

from flowline.core.registry import resolve_step
from flowline.transforms.aggregate.windows import fold_partition_metrics


def run_steps(step_keys, rows):
    """Apply registered row transforms in order."""
    for key in step_keys:
        rows = resolve_step(key)(rows)
    return rows


def run_summary(rows):
    """Terminal stage: fold measurements and report per-partition totals."""
    totals = fold_partition_metrics(rows)
    return {"totals": totals, "partitions": len(totals)}
'''

CHANGED_FILES["flowline/core/registry.py"] = '''"""String-keyed step registry.

Pipeline specs reference steps by key; values are ``module:function``
dotted paths resolved lazily so spec files stay plain data.
"""

import importlib

from flowline.core.errors import RegistryError

STEP_REGISTRY = {
    "trim-whitespace": "flowline.transforms.cleaning.trim_whitespace:trim_whitespace",
    "drop-nulls": "flowline.transforms.cleaning.drop_nulls:drop_nulls",
    "dedupe": "flowline.transforms.cleaning.dedupe:dedupe",
    "currency-convert": "flowline.transforms.enrich.currency_convert:currency_convert",
    "tag-categories": "flowline.transforms.enrich.tag_categories:tag_categories",
    "fold-partitions": "flowline.transforms.aggregate.windows:fold_partition_metrics",
    "legacy-fold": "flowline.util.legacy:fold_partition_metrics_v1",
    "percentile-profile": "flowline.transforms.aggregate.percentiles:percentile_profile",
}


def resolve_step(key):
    """Return the callable registered under *key*."""
    try:
        target = STEP_REGISTRY[key]
    except KeyError:
        raise RegistryError(f"unknown step key: {key!r}") from None
    module_name, _, func_name = target.partition(":")
    module = importlib.import_module(module_name)
    try:
        return getattr(module, func_name)
    except AttributeError:
        raise RegistryError(f"{target!r} does not resolve") from None
'''

CHANGED_FILES["docs/ARCHITECTURE.md"] = '''# Flowline Architecture

Flowline is a batch ETL engine with four layers (readers, transforms,
sinks, and scheduling) held together by a string-keyed step registry.

## Layers

- **readers/** parse raw inputs (CSV, JSON, NDJSON, and friends) into row dicts.
- **transforms/** are pure functions over rows, split into `cleaning/`,
  `enrich/`, and `aggregate/` stages.
- **sinks/** serialize processed rows to their destinations.
- **scheduling/** owns cron parsing, retry policy, and the job bodies.
- **core/** provides the run context, error types, the step registry, and
  the pipeline driver that wires the layers together.

## Aggregation

The totals rollup lives in `flowline.transforms.aggregate.windows`:
`fold_partition_metrics` collapses `(partition, value)` measurements into
per-partition totals, and every digest surface (CLI, weekly report, digest
sink, nightly job) funnels through it. The frozen v1 shim
`fold_partition_metrics_v1` in `flowline/util/legacy.py` predates the
per-partition breakdown and is kept only for the v1 importers.

## Registry

`flowline/core/registry.py` maps step keys (e.g. `fold-partitions`) to
`module:function` dotted paths, resolved lazily with importlib so pipeline
specs stay plain data.
'''

# ---------------------------------------------------------------------------
# Decoy files: confusingly similar names that must stay byte-identical.
# ---------------------------------------------------------------------------

DECOY_FILES: dict[str, str] = {}

DECOY_FILES["flowline/util/legacy.py"] = '''"""Deprecated v1 shims kept for the frozen importers. Do not extend."""


def fold_partition_metrics_v1(rows):
    """v1 grand-total fold: one float, no per-partition breakdown."""
    return float(sum(float(value) for _, value in rows))


def fold_partition_metrics_legacy(rows, buffer_factor=1.15):
    """Pre-v1 fold with the padding factor the old importers expected."""
    return fold_partition_metrics_v1(rows) * buffer_factor
'''

DECOY_FILES["flowline/util/mathx.py"] = '''"""Small numeric helpers with no engine dependencies."""


def partition_fold_metrics(values, chunk=4):
    """Chunk *values* and sum each chunk (unrelated to the aggregate fold)."""
    # CANARY: amber-lattice
    chunks = [values[i:i + chunk] for i in range(0, len(values), chunk)]
    return [sum(part) for part in chunks]


def safe_ratio(numerator, denominator):
    """Divide, returning 0.0 instead of raising on a zero denominator."""
    return numerator / denominator if denominator else 0.0
'''

DECOY_FILES["flowline/transforms/aggregate/experimental.py"] = '''"""Experimental refold strategies. Nothing here is wired into the registry."""


def refold_partition_metrics(rows, passes=2):
    """Iterated refold prototype; keep byte-stable for the A/B harness."""
    # CANARY: umber-trellis
    result = list(rows)
    for _ in range(passes):
        result = [(name, float(value)) for name, value in result]
    return result


def unfold_partition_metrics(totals):
    """Inverse-ish of the fold: expand totals back into single-entry rows."""
    return [(name, total) for name, total in sorted(totals.items())]
'''

DECOY_FILES["flowline/transforms/aggregate/stats.py"] = '''"""Descriptive statistics over partitioned measurements."""


def fold_partition_stats(rows):
    """Per-partition min/max/count. Not the totals rollup; see windows.py."""
    stats = {}
    for partition, value in rows:
        entry = stats.setdefault(partition, {"min": value, "max": value, "count": 0})
        entry["min"] = min(entry["min"], value)
        entry["max"] = max(entry["max"], value)
        entry["count"] += 1
    return stats


def fold_partition_series(rows):
    """Group raw values per partition without collapsing them."""
    series = {}
    for partition, value in rows:
        series.setdefault(partition, []).append(value)
    return series
'''

DECOY_FILES["flowline/transforms/aggregate/grouping.py"] = '''"""Alternate grouping primitives kept for comparison benchmarks."""


def fold_metric_partitions(rows):
    """Group by value bucket instead of partition name (benchmark variant)."""
    buckets = {}
    for partition, value in rows:
        buckets.setdefault(round(float(value)), []).append(partition)
    return buckets
'''

DECOY_FILES["flowline/config/schema.py"] = '''"""Config schema constants and the legacy step-name allowlist."""

REQUIRED_KEYS = ("source", "steps", "sink")

LEGACY_STEP_NAMES = [
    "fold_partition_metrics_v1",
    "fold_partition_stats",
    "partition_fold_metrics",
]


def validate(spec):
    """Cheap structural validation; raises KeyError on missing keys."""
    for key in REQUIRED_KEYS:
        if key not in spec:
            raise KeyError(f"pipeline spec missing {key!r}")
    return dict(spec)
'''

# ---------------------------------------------------------------------------
# Neutral boilerplate: everything else in the tree.
# ---------------------------------------------------------------------------

NEUTRAL_FILES: dict[str, str] = {}

NEUTRAL_FILES["flowline/__init__.py"] = '''"""Flowline: a small batch ETL engine (readers -> transforms -> sinks)."""

__version__ = "1.4.2"
'''

NEUTRAL_FILES["flowline/core/__init__.py"] = '''"""Engine core: context, errors, registry, pipeline driver."""
'''

NEUTRAL_FILES["flowline/core/errors.py"] = '''"""Exception hierarchy for the engine."""


class FlowlineError(Exception):
    """Base class for engine failures."""


class ReaderError(FlowlineError):
    """Raised when an input source cannot be parsed."""


class SinkError(FlowlineError):
    """Raised when an output target rejects rows."""


class RegistryError(FlowlineError):
    """Raised when a step key cannot be resolved to a callable."""
'''

NEUTRAL_FILES["flowline/core/context.py"] = '''"""Run context threaded through pipeline stages."""


class RunContext:
    """Carries run id, dry-run flag, and accumulated warnings."""

    def __init__(self, run_id, dry_run=False):
        self.run_id = run_id
        self.dry_run = dry_run
        self.warnings = []

    def warn(self, message):
        self.warnings.append(str(message))
        return message
'''

NEUTRAL_FILES["flowline/core/types.py"] = '''"""Shared type aliases for pipeline stages."""

Row = dict
Rows = list
StepKey = str
DottedPath = str
'''

NEUTRAL_FILES["flowline/config/__init__.py"] = '''"""Configuration loading and defaults."""
'''

NEUTRAL_FILES["flowline/config/defaults.py"] = '''"""Built-in pipeline defaults used when a spec omits fields."""

DEFAULT_STEPS = ["trim-whitespace", "drop-nulls", "dedupe"]
NIGHTLY_STEPS = ["trim-whitespace", "fold-partitions"]
DEFAULT_SINK = "stdout"
DEFAULT_PRECISION = 2
'''

NEUTRAL_FILES["flowline/config/loader.py"] = '''"""Parse `key=value` spec files into plain dicts."""


def load_spec(path):
    """Read a spec file; later keys win, comments start with `#`."""
    spec = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            spec[key.strip()] = value.strip()
    return spec
'''

NEUTRAL_FILES["flowline/config/env.py"] = '''"""Environment-variable overrides for pipeline specs."""

import os

PREFIX = "FLOWLINE_"


def env_overrides(environ=None):
    """Collect FLOWLINE_* variables as lower-cased spec keys."""
    source = environ if environ is not None else os.environ
    return {
        key[len(PREFIX):].lower(): value
        for key, value in sorted(source.items())
        if key.startswith(PREFIX)
    }
'''

NEUTRAL_FILES["flowline/config/paths.py"] = '''"""Well-known filesystem locations for pipeline state."""

from pathlib import Path


def state_dir(base=None):
    """Directory for run bookkeeping; created on first use."""
    root = Path(base) if base else Path.home() / ".flowline"
    root.mkdir(parents=True, exist_ok=True)
    return root


def runs_dir(base=None):
    """Subdirectory holding one folder per pipeline run."""
    return state_dir(base) / "runs"
'''

NEUTRAL_FILES["flowline/readers/__init__.py"] = '''"""Input readers: one module per source format."""
'''

NEUTRAL_FILES["flowline/transforms/cleaning/__init__.py"] = '''"""Row-cleaning transforms."""

from flowline.transforms.cleaning.dedupe import dedupe
from flowline.transforms.cleaning.drop_nulls import drop_nulls
from flowline.transforms.cleaning.trim_whitespace import trim_whitespace

__all__ = ["dedupe", "drop_nulls", "trim_whitespace"]
'''

NEUTRAL_FILES["flowline/transforms/enrich/__init__.py"] = '''"""Row-enrichment transforms."""
'''

NEUTRAL_FILES["flowline/transforms/aggregate/percentiles.py"] = '''"""Percentile summaries used by the ad-hoc reports."""


def percentile_profile(values, cuts=(50, 90, 99)):
    """Nearest-rank percentiles for *values* at each cut point."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {cut: 0.0 for cut in cuts}
    profile = {}
    for cut in cuts:
        rank = max(0, min(len(ordered) - 1, round(cut / 100 * len(ordered)) - 1))
        profile[cut] = ordered[rank]
    return profile
'''

NEUTRAL_FILES["flowline/sinks/__init__.py"] = '''"""Output sinks: one module per destination format."""
'''

NEUTRAL_FILES["flowline/scheduling/__init__.py"] = '''"""Scheduling: cron parsing, calendars, retry policy, job bodies."""
'''

NEUTRAL_FILES["flowline/scheduling/cron.py"] = '''"""Minimal five-field cron expression parsing."""

FIELDS = ("minute", "hour", "day", "month", "weekday")


def parse_cron(expression):
    """Split a cron expression into a field dict; `*` means every."""
    parts = expression.split()
    if len(parts) != len(FIELDS):
        raise ValueError(f"expected {len(FIELDS)} cron fields, got {len(parts)}")
    return dict(zip(FIELDS, parts))


def is_wildcard(field_value):
    """True when a cron field matches every slot."""
    return field_value in ("*", "*/1")
'''

NEUTRAL_FILES["flowline/scheduling/calendar_rules.py"] = '''"""Business-calendar rules layered on top of cron schedules."""

WEEKEND = (5, 6)


def is_business_day(weekday_index):
    """Monday=0 ... Sunday=6; weekends are not business days."""
    return weekday_index not in WEEKEND


def next_business_day(weekday_index):
    """Index of the next business day after *weekday_index*."""
    candidate = (weekday_index + 1) % 7
    while not is_business_day(candidate):
        candidate = (candidate + 1) % 7
    return candidate
'''

NEUTRAL_FILES["flowline/scheduling/retry.py"] = '''"""Bounded retry helper for flaky deliveries."""


def with_retry(func, attempts=3):
    """Call *func* until it stops raising, at most *attempts* times."""
    last_error = None
    for _ in range(max(1, attempts)):
        try:
            return func()
        except Exception as error:  # noqa: BLE001, deliberate catch-all
            last_error = error
    raise last_error
'''

NEUTRAL_FILES["flowline/scheduling/backoff.py"] = '''"""Deterministic backoff schedules (no jitter: tests need stable timing)."""


def exponential_backoff(attempt, base_seconds=1.0, cap_seconds=60.0):
    """Delay before retry *attempt* (0-indexed), capped at *cap_seconds*."""
    return min(cap_seconds, base_seconds * (2 ** attempt))


def backoff_schedule(attempts, base_seconds=1.0):
    """The full delay sequence for *attempts* retries."""
    return [exponential_backoff(i, base_seconds) for i in range(attempts)]
'''

NEUTRAL_FILES["flowline/reporting/weekly_notes.py"] = '''"""Free-form notes appended to the weekly digest email."""


def render_notes(notes):
    """Bulleted plain-text block from a list of note strings."""
    return "\\n".join(f"  * {note.strip()}" for note in notes if note.strip())
'''

NEUTRAL_FILES["flowline/reporting/monthly.py"] = '''"""Monthly rollups assembled from the weekly digests."""


def month_header(year, month):
    """Stable section header for a monthly report."""
    return f"== {year:04d}-{month:02d} =="


def combine_weeks(weekly_lines):
    """Join weekly digest lines into one monthly block."""
    return "\\n".join(line for line in weekly_lines if line)
'''

NEUTRAL_FILES["flowline/reporting/adhoc.py"] = '''"""Ad-hoc percentile reports for on-call spelunking."""

from flowline.transforms.aggregate.percentiles import percentile_profile


def latency_report(samples):
    """Render p50/p90/p99 of *samples* as a single line."""
    profile = percentile_profile(samples)
    return " ".join(f"p{cut}={value:.1f}" for cut, value in sorted(profile.items()))
'''

NEUTRAL_FILES["flowline/reporting/formats.py"] = '''"""Tiny formatting helpers shared by the report renderers."""


def align_columns(pairs, gap=2):
    """Left-align `(label, value)` pairs into two tidy columns."""
    if not pairs:
        return ""
    width = max(len(str(label)) for label, _ in pairs) + gap
    return "\\n".join(f"{str(label).ljust(width)}{value}" for label, value in pairs)
'''

NEUTRAL_FILES["flowline/util/__init__.py"] = '''"""Dependency-free helpers shared across layers."""
'''

NEUTRAL_FILES["flowline/util/iterx.py"] = '''"""Iteration helpers that keep memory flat."""


def chunked(items, size):
    """Yield *items* in lists of at most *size*."""
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def first(items, default=None):
    """First element or *default* when empty."""
    for item in items:
        return item
    return default
'''

NEUTRAL_FILES["flowline/util/pathx.py"] = '''"""Path helpers for run artifacts."""

from pathlib import Path


def ensure_parent(path):
    """Create the parent directory of *path*; returns the Path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def with_suffix_stamped(path, stamp):
    """`report.csv` + `2024w07` -> `report.2024w07.csv`."""
    target = Path(path)
    return target.with_name(f"{target.stem}.{stamp}{target.suffix}")
'''

NEUTRAL_FILES["flowline/util/textx.py"] = '''"""Text helpers for identifiers and labels."""


def slugify(label):
    """Lower-case *label* and collapse runs of non-alphanumerics to `-`."""
    out = []
    previous_dash = False
    for char in str(label).lower():
        if char.isalnum():
            out.append(char)
            previous_dash = False
        elif not previous_dash:
            out.append("-")
            previous_dash = True
    return "".join(out).strip("-")


def truncate(text, limit=80, ellipsis="..."):
    """Clip *text* to *limit* characters, appending *ellipsis* when clipped."""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(ellipsis))] + ellipsis
'''

NEUTRAL_FILES["flowline/util/timers.py"] = '''"""Manual stopwatch used by the pipeline driver for stage timing."""


class Stopwatch:
    """Accumulates externally supplied tick durations (no wall-clock)."""

    def __init__(self):
        self.laps = []

    def record(self, seconds):
        self.laps.append(float(seconds))
        return self

    def total(self):
        return round(sum(self.laps), 6)
'''

NEUTRAL_FILES["docs/PIPELINES.md"] = '''# Writing Pipeline Specs

A pipeline spec is plain data: a source, an ordered list of step keys,
and a sink. Step keys resolve through the registry in
`flowline/core/registry.py`.

## Step keys

| Key | Stage |
|---|---|
| `trim-whitespace` | cleaning |
| `drop-nulls` | cleaning |
| `dedupe` | cleaning |
| `currency-convert` | enrich |
| `tag-categories` | enrich |
| `fold-partitions` | aggregate |
| `legacy-fold` | aggregate (frozen v1 shim) |
| `percentile-profile` | aggregate |

Keys are stable identifiers: renaming an implementation function must not
change its key. The frozen names in `LEGACY_STEP_NAMES`
(`flowline/config/schema.py`) are reserved forever.
'''

NEUTRAL_FILES["docs/CONTRIBUTING.md"] = '''# Contributing

- One transform per module; keep functions pure (rows in, rows out).
- Every public function carries a docstring with an example when the
  behavior is not obvious from the signature.
- New steps register a key in `flowline/core/registry.py` and document it
  in `docs/PIPELINES.md`.
- Never repurpose a legacy shim: the modules under `flowline/util/` marked
  "do not extend" are byte-frozen for the v1 importers.
'''

READERS = [
    ("CSV", "read_csv", ".csv", ","),
    ("JSON", "read_json", ".json", ":"),
    ("NDJSON", "read_ndjson", ".ndjson", ":"),
    ("Parquet-lite", "read_parquet", ".parquet", "|"),
    ("Avro-lite", "read_avro", ".avro", "|"),
    ("XML export", "read_xml", ".xml", ">"),
    ("HTML table", "read_html_table", ".html", ">"),
    ("Excel export", "read_excel", ".xlsx", "\t"),
    ("fixed-width", "read_fixed_width", ".txt", " "),
    ("SQLite dump", "read_sqlite_dump", ".sql", ";"),
    ("Feather-lite", "read_feather", ".feather", "|"),
    ("ORC-lite", "read_orc", ".orc", "|"),
]
for fmt, func, ext, delim in READERS:
    NEUTRAL_FILES[f"flowline/readers/{func[5:] if func.startswith('read_') else func}_reader.py"] = (
        reader_module(fmt, func, ext, delim)
    )

CLEANERS = [
    (
        "trim_whitespace",
        "leading/trailing whitespace stripped from every string value.",
        "    return [\n"
        "        {key: value.strip() if isinstance(value, str) else value for key, value in row.items()}\n"
        "        for row in rows\n"
        "    ]",
    ),
    (
        "drop_nulls",
        "rows containing any None value removed.",
        "    return [row for row in rows if all(value is not None for value in row.values())]",
    ),
    (
        "dedupe",
        "exact duplicate rows collapsed, first occurrence wins.",
        "    seen = set()\n"
        "    unique = []\n"
        "    for row in rows:\n"
        "        key = tuple(sorted(row.items()))\n"
        "        if key not in seen:\n"
        "            seen.add(key)\n"
        "            unique.append(row)\n"
        "    return unique",
    ),
    (
        "normalize_case",
        "string values lower-cased for stable joins.",
        "    return [\n"
        "        {key: value.lower() if isinstance(value, str) else value for key, value in row.items()}\n"
        "        for row in rows\n"
        "    ]",
    ),
    (
        "coerce_types",
        "numeric-looking strings coerced to floats.",
        "    def coerce(value):\n"
        "        if isinstance(value, str):\n"
        "            try:\n"
        "                return float(value)\n"
        "            except ValueError:\n"
        "                return value\n"
        "        return value\n"
        "\n"
        "    return [{key: coerce(value) for key, value in row.items()} for row in rows]",
    ),
    (
        "clamp_outliers",
        "numeric values clamped into [-1e9, 1e9].",
        "    def clamp(value):\n"
        "        if isinstance(value, (int, float)):\n"
        "            return max(-1e9, min(1e9, value))\n"
        "        return value\n"
        "\n"
        "    return [{key: clamp(value) for key, value in row.items()} for row in rows]",
    ),
    (
        "fill_defaults",
        "None values replaced by empty strings.",
        "    return [\n"
        "        {key: \"\" if value is None else value for key, value in row.items()}\n"
        "        for row in rows\n"
        "    ]",
    ),
    (
        "strip_currency",
        "currency symbols stripped from string values.",
        "    symbols = \"$€£¥\"\n"
        "    return [\n"
        "        {key: value.strip(symbols) if isinstance(value, str) else value for key, value in row.items()}\n"
        "        for row in rows\n"
        "    ]",
    ),
    (
        "parse_dates",
        "ISO `YYYY-MM-DD` strings split into year/month/day ints.",
        "    parsed = []\n"
        "    for row in rows:\n"
        "        updated = dict(row)\n"
        "        value = row.get(\"date\")\n"
        "        if isinstance(value, str) and len(value) == 10 and value[4] == value[7] == \"-\":\n"
        "            updated[\"year\"], updated[\"month\"], updated[\"day\"] = (\n"
        "                int(value[:4]), int(value[5:7]), int(value[8:10])\n"
        "            )\n"
        "        parsed.append(updated)\n"
        "    return parsed",
    ),
    (
        "rename_headers",
        "header keys slug-cased (spaces to underscores, lower).",
        "    return [\n"
        "        {str(key).strip().lower().replace(\" \", \"_\"): value for key, value in row.items()}\n"
        "        for row in rows\n"
        "    ]",
    ),
]
for func, summary, body in CLEANERS:
    NEUTRAL_FILES[f"flowline/transforms/cleaning/{func}.py"] = cleaning_module(func, summary, body)

ENRICHERS = [
    ("annotate_source", "stamp the originating system", "source_system", '"flowline"'),
    ("bucket_ages", "coarse age bucket from an `age` field", "age_bucket",
     '"minor" if float(row.get("age", 0) or 0) < 18 else "adult"'),
    ("currency_convert", "convert `amount` to cents", "amount_cents",
     'int(round(float(row.get("amount", 0) or 0) * 100))'),
    ("derive_ratios", "amount-per-unit ratio", "amount_per_unit",
     'float(row.get("amount", 0) or 0) / max(1.0, float(row.get("units", 1) or 1))'),
    ("expand_codes", "split a `codes` CSV field into a list", "code_list",
     'str(row.get("codes", "")).split(",") if row.get("codes") else []'),
    ("geo_lookup", "coarse region from a `country` field", "region",
     '"emea" if str(row.get("country", "")).upper() in ("DE", "FR", "GB") else "other"'),
    ("hash_ids", "stable short id from the row repr", "row_id",
     'format(abs(hash(tuple(sorted(str(item) for item in row.items())))) % 10**8, "08d")'),
    ("join_reference", "attach the static plan tier", "plan_tier",
     '{"p1": "gold", "p2": "silver"}.get(str(row.get("plan", "")), "bronze")'),
    ("score_quality", "fraction of non-empty fields", "quality",
     'round(sum(1 for value in row.values() if value not in (None, "")) / max(1, len(row)), 3)'),
    ("tag_categories", "size category from a `units` field", "category",
     '"bulk" if float(row.get("units", 0) or 0) >= 100 else "retail"'),
]
for func, summary, key, expr in ENRICHERS:
    NEUTRAL_FILES[f"flowline/transforms/enrich/{func}.py"] = enrich_module(func, summary, key, expr)

SINKS = [
    ("CSV", "write_csv", '",".join(str(value) for value in row.values())'),
    ("JSON lines", "write_jsonl", "__import__('json').dumps(row, sort_keys=True)"),
    ("pretty JSON", "write_json", "__import__('json').dumps(row, sort_keys=True, indent=2)"),
    ("TSV", "write_tsv", '"\\t".join(str(value) for value in row.values())'),
    ("key=value pairs", "write_kv", '" ".join(f"{key}={value}" for key, value in sorted(row.items()))'),
    ("aligned text", "write_table", '" | ".join(str(value).ljust(12) for value in row.values())'),
    ("SQL inserts", "write_sql_inserts",
     '"INSERT INTO rows VALUES (" + ", ".join(repr(str(value)) for value in row.values()) + ");"'),
    ("markdown rows", "write_markdown", '"| " + " | ".join(str(value) for value in row.values()) + " |"'),
]
for fmt, func, line_expr in SINKS:
    module = func[6:] if func.startswith("write_") else func
    NEUTRAL_FILES[f"flowline/sinks/{module}_sink.py"] = sink_module(fmt, func, line_expr)


def build_trees() -> tuple[dict[str, str], dict[str, str]]:
    """Return (fixture_files, solution_files) as relpath -> content."""
    fixture = {}
    fixture.update(NEUTRAL_FILES)
    fixture.update(DECOY_FILES)
    fixture.update(CHANGED_FILES)
    solution = {rel: OLD_WORD.sub(NEW, content) for rel, content in CHANGED_FILES.items()}
    return fixture, solution


def write_tree(base: Path, files: dict[str, str]) -> str:
    if base.exists():
        shutil.rmtree(base)
    digest = hashlib.sha256()
    for rel in sorted(files):
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[rel], encoding="utf-8", newline="\n")
        digest.update(rel.encode())
        digest.update(files[rel].encode())
    return digest.hexdigest()[:16]


def main() -> None:
    fixture, solution = build_trees()
    fixture_hash = write_tree(ROOT / "fixture", fixture)
    solution_hash = write_tree(ROOT / "solution", solution)
    canary_hits = sum(1 for content in fixture.values() if "CANARY: umber-lattice" in content)
    old_ref_files = sum(1 for content in fixture.values() if OLD_WORD.search(content))
    assert canary_hits == 1, f"exact canary must appear in exactly 1 file, found {canary_hits}"
    assert old_ref_files == len(CHANGED_FILES), (
        f"word-boundary OLD refs in {old_ref_files} files, expected {len(CHANGED_FILES)}"
    )
    assert not any(OLD_WORD.search(content) for content in solution.values()), "solution still holds OLD"
    print(f"fixture: {len(fixture)} files, tree sha256 {fixture_hash}")
    print(f"solution: {len(solution)} files, tree sha256 {solution_hash}")


if __name__ == "__main__":
    main()
