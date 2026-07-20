"""TTL + LRU cache. See README.md for the full specification."""

import time


class TTLCache:
    def __init__(self, max_size, default_ttl, clock=time.monotonic):
        raise NotImplementedError

    def set(self, key, value, ttl=None):
        raise NotImplementedError

    def get(self, key, default=None):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

    def purge(self):
        raise NotImplementedError

    def stats(self):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def __contains__(self, key):
        raise NotImplementedError
