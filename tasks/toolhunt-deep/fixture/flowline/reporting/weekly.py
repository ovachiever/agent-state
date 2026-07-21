"""Weekly digest lines for the ops channel."""

from flowline.transforms.aggregate import fold_partition_metrics


def partition_digest(rows):
    """Render folded totals as `name=total` joined with pipes."""
    totals = fold_partition_metrics(rows)
    return " | ".join(f"{name}={total:.2f}" for name, total in totals.items())
