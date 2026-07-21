"""Parse `key=value` spec files into plain dicts."""


def load_spec(path):
    """Read a spec file; later keys win, comments start with `#`."""
    spec = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            spec[key.strip()] = value.strip()
    return spec
