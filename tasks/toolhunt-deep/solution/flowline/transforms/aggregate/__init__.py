"""Aggregation transforms."""

from flowline.transforms.aggregate.grouping import fold_metric_partitions
from flowline.transforms.aggregate.percentiles import percentile_profile
from flowline.transforms.aggregate.stats import fold_partition_series, fold_partition_stats
from flowline.transforms.aggregate.windows import consolidate_partition_metrics, windowed_rollup

__all__ = [
    "fold_metric_partitions",
    "percentile_profile",
    "fold_partition_series",
    "fold_partition_stats",
    "consolidate_partition_metrics",
    "windowed_rollup",
]
