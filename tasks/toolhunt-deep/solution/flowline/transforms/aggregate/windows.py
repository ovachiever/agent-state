"""Windowed aggregation over partitioned measurements."""


def consolidate_partition_metrics(rows, precision=2):
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
    folded = sorted(consolidate_partition_metrics(rows).items())
    return [dict(folded[i:i + width]) for i in range(0, len(folded), width)]
