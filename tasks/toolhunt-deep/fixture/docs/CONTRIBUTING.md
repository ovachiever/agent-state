# Contributing

- One transform per module; keep functions pure (rows in, rows out).
- Every public function carries a docstring with an example when the
  behavior is not obvious from the signature.
- New steps register a key in `flowline/core/registry.py` and document it
  in `docs/PIPELINES.md`.
- Never repurpose a legacy shim: the modules under `flowline/util/` marked
  "do not extend" are byte-frozen for the v1 importers.
