"""Nightly and weekly job bodies invoked by the scheduler."""

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
