"""Built-in pipeline defaults used when a spec omits fields."""

DEFAULT_STEPS = ["trim-whitespace", "drop-nulls", "dedupe"]
NIGHTLY_STEPS = ["trim-whitespace", "fold-partitions"]
DEFAULT_SINK = "stdout"
DEFAULT_PRECISION = 2
