"""Alternate grouping primitives kept for comparison benchmarks."""


def fold_metric_partitions(rows):
    """Group by value bucket instead of partition name (benchmark variant)."""
    buckets = {}
    for partition, value in rows:
        buckets.setdefault(round(float(value)), []).append(partition)
    return buckets
