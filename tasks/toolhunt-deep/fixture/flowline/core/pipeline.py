"""Pipeline orchestration: resolve steps, run them, summarize."""

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
