# Flowline Architecture

Flowline is a batch ETL engine with four layers (readers, transforms,
sinks, and scheduling) held together by a string-keyed step registry.

## Layers

- **readers/** parse raw inputs (CSV, JSON, NDJSON, and friends) into row dicts.
- **transforms/** are pure functions over rows, split into `cleaning/`,
  `enrich/`, and `aggregate/` stages.
- **sinks/** serialize processed rows to their destinations.
- **scheduling/** owns cron parsing, retry policy, and the job bodies.
- **core/** provides the run context, error types, the step registry, and
  the pipeline driver that wires the layers together.

## Aggregation

The totals rollup lives in `flowline.transforms.aggregate.windows`:
`fold_partition_metrics` collapses `(partition, value)` measurements into
per-partition totals, and every digest surface (CLI, weekly report, digest
sink, nightly job) funnels through it. The frozen v1 shim
`fold_partition_metrics_v1` in `flowline/util/legacy.py` predates the
per-partition breakdown and is kept only for the v1 importers.

## Registry

`flowline/core/registry.py` maps step keys (e.g. `fold-partitions`) to
`module:function` dotted paths, resolved lazily with importlib so pipeline
specs stay plain data.
