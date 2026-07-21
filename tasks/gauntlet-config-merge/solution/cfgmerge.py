"""cfgmerge: layered JSON config merger for the deploy pipeline."""

import argparse
import json
import sys

DELETE = "$delete"


class ConflictError(Exception):
    def __init__(self, path, old_type, new_type):
        super().__init__(path)
        self.path = path
        self.old_type = old_type
        self.new_type = new_type


def _type_name(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if value is None:
        return "null"
    return "unknown"


def _is_delete(value):
    return isinstance(value, str) and value == DELETE


def _merge_pair(old, new, strict, path):
    if _is_delete(new) or _is_delete(old):
        return new
    if isinstance(old, dict) and isinstance(new, dict):
        merged = dict(old)
        for key, value in new.items():
            child = f"{path}.{key}" if path else key
            if key in merged:
                merged[key] = _merge_pair(merged[key], value, strict, child)
            else:
                merged[key] = value
        return merged
    if strict and _type_name(old) != _type_name(new):
        raise ConflictError(path, _type_name(old), _type_name(new))
    return new


def _strip_deletes(value):
    if isinstance(value, dict):
        return {
            k: _strip_deletes(v) for k, v in value.items() if not _is_delete(v)
        }
    return value


def merge_configs(layers, strict=False):
    merged = {}
    for layer in layers:
        merged = _merge_pair(merged, layer, strict, "")
    return _strip_deletes(merged)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cfgmerge")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--version", action="version", version="cfgmerge 2.1.0")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)

    layers = []
    for path in args.files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            print(f"error: cannot read {path}", file=sys.stderr)
            return 2
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print(f"error: invalid JSON in {path}", file=sys.stderr)
            return 3
        if not isinstance(data, dict):
            print(f"error: top-level value in {path} must be an object", file=sys.stderr)
            return 5
        layers.append(data)

    try:
        merged = merge_configs(layers, strict=args.strict)
    except ConflictError as e:
        print(
            f"error: type conflict at {e.path}: {e.old_type} vs {e.new_type}",
            file=sys.stderr,
        )
        return 4

    sys.stdout.write(json.dumps(merged, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
