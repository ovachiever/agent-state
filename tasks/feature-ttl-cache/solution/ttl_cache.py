"""TTL + LRU cache. See README.md for the full specification."""

import time
from collections import OrderedDict


class TTLCache:
    def __init__(self, max_size, default_ttl, clock=time.monotonic):
        if not isinstance(max_size, int) or max_size < 1:
            raise ValueError("max_size must be an int >= 1")
        if default_ttl <= 0:
            raise ValueError("default_ttl must be > 0")
        self._max = max_size
        self._default_ttl = default_ttl
        self._clock = clock
        self._data = OrderedDict()  # key -> (value, expiry); last item = MRU
        self._hits = self._misses = self._evictions = self._expirations = 0

    def _is_expired(self, expiry):
        return self._clock() >= expiry

    def set(self, key, value, ttl=None):
        if ttl is None:
            ttl = self._default_ttl
        elif ttl <= 0:
            raise ValueError("ttl must be > 0")
        if key in self._data:
            self._data[key] = (value, self._clock() + ttl)
            self._data.move_to_end(key)
            return
        if len(self._data) >= self._max:
            expired = [(exp, k) for k, (_, exp) in self._data.items() if self._is_expired(exp)]
            if expired:
                _, victim = min(expired)
                del self._data[victim]
                self._expirations += 1
            else:
                self._data.popitem(last=False)
                self._evictions += 1
        self._data[key] = (value, self._clock() + ttl)

    def get(self, key, default=None):
        entry = self._data.get(key)
        if entry is None:
            self._misses += 1
            return default
        value, expiry = entry
        if self._is_expired(expiry):
            del self._data[key]
            self._expirations += 1
            self._misses += 1
            return default
        self._data.move_to_end(key)
        self._hits += 1
        return value

    def delete(self, key):
        if key in self._data:
            del self._data[key]
            return True
        return False

    def purge(self):
        victims = [k for k, (_, exp) in self._data.items() if self._is_expired(exp)]
        for k in victims:
            del self._data[k]
        self._expirations += len(victims)
        return len(victims)

    def stats(self):
        return {
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "expirations": self._expirations,
        }

    def __len__(self):
        return sum(1 for _, exp in self._data.values() if not self._is_expired(exp))

    def __contains__(self, key):
        entry = self._data.get(key)
        return entry is not None and not self._is_expired(entry[1])
