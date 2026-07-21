"""Digest sink: folded totals as `partition,total` lines."""

from flowline.transforms.aggregate import consolidate_partition_metrics


def write_digest(rows, stream):
    """Fold *rows* and write one `partition,total` line per partition."""
    totals = consolidate_partition_metrics(rows)
    for name, total in totals.items():
        stream.write(f"{name},{total:.2f}\n")
    return len(totals)
