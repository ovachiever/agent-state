"""Config schema constants and the legacy step-name allowlist."""

REQUIRED_KEYS = ("source", "steps", "sink")

LEGACY_STEP_NAMES = [
    "fold_partition_metrics_v1",
    "fold_partition_stats",
    "partition_fold_metrics",
]


def validate(spec):
    """Cheap structural validation; raises KeyError on missing keys."""
    for key in REQUIRED_KEYS:
        if key not in spec:
            raise KeyError(f"pipeline spec missing {key!r}")
    return dict(spec)
