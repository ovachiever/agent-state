# Writing Pipeline Specs

A pipeline spec is plain data: a source, an ordered list of step keys,
and a sink. Step keys resolve through the registry in
`flowline/core/registry.py`.

## Step keys

| Key | Stage |
|---|---|
| `trim-whitespace` | cleaning |
| `drop-nulls` | cleaning |
| `dedupe` | cleaning |
| `currency-convert` | enrich |
| `tag-categories` | enrich |
| `fold-partitions` | aggregate |
| `legacy-fold` | aggregate (frozen v1 shim) |
| `percentile-profile` | aggregate |

Keys are stable identifiers: renaming an implementation function must not
change its key. The frozen names in `LEGACY_STEP_NAMES`
(`flowline/config/schema.py`) are reserved forever.
