"""Deprecated v1 shims kept for the frozen importers. Do not extend."""


def fold_partition_metrics_v1(rows):
    """v1 grand-total fold: one float, no per-partition breakdown."""
    return float(sum(float(value) for _, value in rows))


def fold_partition_metrics_legacy(rows, buffer_factor=1.15):
    """Pre-v1 fold with the padding factor the old importers expected."""
    return fold_partition_metrics_v1(rows) * buffer_factor
