# textpipe

Tiny composable text transforms with a central registry.

```bash
python -m textpipe.cli squeeze "  hello    world  "
```

## Adding a transform

Every item is required; the wiring is checked in review.

1. Create `textpipe/transforms/<name>.py` containing exactly one class, subclassing `Transform` from `textpipe.transforms.base`.
2. The class docstring is a single line of the form `<name>: <what it does>.` — lowercase after the colon, ending with a period, matching the existing transforms.
3. Set the `name` class attribute to the transform's name string.
4. Register it in `textpipe/registry.py`: add the import AND the `REGISTRY` entry, keeping both lists alphabetical by transform name.
5. Update the `EPILOG` string in `textpipe/cli.py` so the transform list stays complete, alphabetical, and comma-separated.

Do not modify existing transforms or the base class while adding a new one.
