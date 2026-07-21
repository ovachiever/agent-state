"""Environment-variable overrides for pipeline specs."""

import os

PREFIX = "FLOWLINE_"


def env_overrides(environ=None):
    """Collect FLOWLINE_* variables as lower-cased spec keys."""
    source = environ if environ is not None else os.environ
    return {
        key[len(PREFIX):].lower(): value
        for key, value in sorted(source.items())
        if key.startswith(PREFIX)
    }
