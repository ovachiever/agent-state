"""Hidden verifier for toolhunt-deep. Usage: verify.py <workspace>"""

import json
import re
import subprocess
import sys
from pathlib import Path

OLD = "fold_partition_metrics"
NEW = "consolidate_partition_metrics"
CANARY = "CANARY: umber-lattice"
# Word-boundary match so decoys that merely contain OLD as a substring
# (fold_partition_metrics_v1, unfold_partition_metrics, ...) do not count.
OLD_WORD = re.compile(r"(?<![A-Za-z0-9_])fold_partition_metrics(?![A-Za-z0-9_])")

WINDOWS = "flowline/transforms/aggregate/windows.py"

# Confusingly named neighbors: a blind global replace corrupts these.
DECOY_FILES = [
    "flowline/util/legacy.py",
    "flowline/util/mathx.py",
    "flowline/transforms/aggregate/experimental.py",
    "flowline/transforms/aggregate/stats.py",
    "flowline/transforms/aggregate/grouping.py",
    "flowline/config/schema.py",
]

# Unrelated sample spread across the tree (byte-identical to fixture).
MUST_NOT_CHANGE = [
    "flowline/__init__.py",
    "flowline/config/defaults.py",
    "flowline/config/loader.py",
    "flowline/core/context.py",
    "flowline/core/errors.py",
    "flowline/core/types.py",
    "flowline/readers/csv_reader.py",
    "flowline/readers/json_reader.py",
    "flowline/transforms/cleaning/dedupe.py",
    "flowline/transforms/enrich/currency_convert.py",
    "flowline/sinks/csv_sink.py",
    "flowline/scheduling/cron.py",
    "flowline/scheduling/retry.py",
    "flowline/reporting/monthly.py",
    "flowline/util/timers.py",
    "docs/PIPELINES.md",
]

SMOKE = """
import io
import sys
sys.path.insert(0, sys.argv[1])
rows = [("us-east", 10.0), ("eu-west", 2.5), ("us-east", 5.25)]
from flowline.transforms.aggregate import consolidate_partition_metrics, windowed_rollup
totals = consolidate_partition_metrics(rows)
assert totals == {"eu-west": 2.5, "us-east": 15.25}, totals
assert windowed_rollup(rows, width=1) == [{"eu-west": 2.5}, {"us-east": 15.25}]
from flowline.reporting import weekly
assert weekly.partition_digest(rows) == "eu-west=2.50 | us-east=15.25"
from flowline import cli
assert cli.summarize(rows) == "2 partitions, grand total 17.75"
from flowline.scheduling.jobs import nightly_rollup_job
assert nightly_rollup_job(rows) == {"partitions": 2, "total": 17.75}
from flowline.sinks.digest import write_digest
buf = io.StringIO()
assert write_digest(rows, buf) == 2 and buf.getvalue() == "eu-west,2.50\\nus-east,15.25\\n"
from flowline.core.pipeline import run_summary
assert run_summary(rows) == {"totals": totals, "partitions": 2}
print("chain-ok")
from flowline.core.registry import resolve_step
assert resolve_step("fold-partitions")(rows) == totals
assert abs(resolve_step("legacy-fold")(rows) - 17.75) < 1e-9
print("registry-ok")
"""


def _walk(ws):
    for path in ws.rglob("*"):
        if path.is_dir() or path.suffix in (".pyc", ".pyo"):
            continue
        # Skip VCS/harness/tool droppings: agents that smoke-test their work
        # leave __pycache__ bytecode that still embeds the old name.
        if any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(ws).parts):
            continue
        yield path


def _text(ws, rel):
    path = ws / rel
    return path.read_text(errors="replace") if path.exists() else ""


def _unchanged(ws, fixture, rels):
    for rel in rels:
        wp, fp = ws / rel, fixture / rel
        if not wp.exists() or wp.read_bytes() != fp.read_bytes():
            return False
    return True


def main():
    ws = Path(sys.argv[1])
    fixture = Path(__file__).parent / "fixture"
    checks = {}

    py_files, other_files = {}, {}
    for path in _walk(ws):
        rel = path.relative_to(ws).as_posix()
        target = py_files if path.suffix == ".py" else other_files
        target[rel] = path.read_text(errors="replace")

    windows_text = py_files.get(WINDOWS, "")
    checks["new_def_in_windows"] = bool(re.search(rf"^def {NEW}\(", windows_text, re.M))
    defs = sorted(rel for rel, text in py_files.items() if re.search(rf"^def {NEW}\(", text, re.M))
    checks["new_def_exactly_once"] = defs == [WINDOWS]
    checks["canary_preserved"] = CANARY in windows_text

    checks["old_name_gone_code"] = not any(OLD_WORD.search(text) for text in py_files.values())
    checks["old_name_gone_docs"] = not any(OLD_WORD.search(text) for text in other_files.values())

    checks["reexport_aggregate_updated"] = NEW in _text(ws, "flowline/transforms/aggregate/__init__.py")
    checks["reexport_transforms_updated"] = NEW in _text(ws, "flowline/transforms/__init__.py")
    checks["callsite_cli_updated"] = NEW in _text(ws, "flowline/cli.py")
    checks["callsite_weekly_updated"] = NEW in _text(ws, "flowline/reporting/weekly.py")
    checks["callsite_jobs_updated"] = NEW in _text(ws, "flowline/scheduling/jobs.py")
    checks["callsite_digest_updated"] = NEW in _text(ws, "flowline/sinks/digest.py")
    checks["callsite_pipeline_updated"] = NEW in _text(ws, "flowline/core/pipeline.py")
    checks["docstring_example_updated"] = f">>> {NEW}(" in _text(ws, "flowline/reporting/__init__.py")

    registry_text = _text(ws, "flowline/core/registry.py")
    checks["registry_string_updated"] = f"flowline.transforms.aggregate.windows:{NEW}" in registry_text
    checks["registry_decoy_intact"] = "flowline.util.legacy:fold_partition_metrics_v1" in registry_text

    arch_text = _text(ws, "docs/ARCHITECTURE.md")
    checks["architecture_doc_updated"] = NEW in arch_text and not OLD_WORD.search(arch_text)
    checks["architecture_decoy_intact"] = f"{OLD}_v1" in arch_text

    checks["decoys_untouched"] = _unchanged(ws, fixture, DECOY_FILES)
    checks["unrelated_untouched"] = _unchanged(ws, fixture, MUST_NOT_CHANGE)

    try:
        proc = subprocess.run(
            [sys.executable, "-c", SMOKE, str(ws)],
            capture_output=True, text=True, timeout=30,
        )
        checks["smoke_chain_passes"] = "chain-ok" in proc.stdout
        checks["smoke_registry_passes"] = proc.returncode == 0 and "registry-ok" in proc.stdout
    except subprocess.TimeoutExpired:
        checks["smoke_chain_passes"] = False
        checks["smoke_registry_passes"] = False

    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"score": 0.0, "checks": {"verifier_crashed": False}}))
