"""Descriptive statistics over partitioned measurements."""


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
