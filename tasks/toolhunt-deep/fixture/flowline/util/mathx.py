"""Small numeric helpers with no engine dependencies."""


def partition_fold_metrics(values, chunk=4):
    """Chunk *values* and sum each chunk (unrelated to the aggregate fold)."""
    # CANARY: amber-lattice
    chunks = [values[i:i + chunk] for i in range(0, len(values), chunk)]
    return [sum(part) for part in chunks]


def safe_ratio(numerator, denominator):
    """Divide, returning 0.0 instead of raising on a zero denominator."""
    return numerator / denominator if denominator else 0.0
