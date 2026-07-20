# TTLCache Specification

Implement `TTLCache` in `ttl_cache.py`. Standard library only.

## Constructor

```python
TTLCache(max_size: int, default_ttl: float, clock=time.monotonic)
```

- `max_size`: maximum number of stored entries (live or expired-but-unpurged). Must be >= 1, else `ValueError`.
- `default_ttl`: seconds an entry lives unless `set()` overrides it. Must be > 0, else `ValueError`.
- `clock`: zero-arg callable returning a float time in seconds. All time reads go through this (never call `time.*` directly), so tests can inject a fake clock.

## Methods

### `set(key, value, ttl=None)`
- Stores `value` under `key`, expiring `ttl` seconds from now (`ttl=None` means use `default_ttl`; an explicit `ttl` must be > 0, else `ValueError`).
- Overwriting an existing live key updates value, expiry, and marks the key most-recently-used. It is not an eviction.
- If the key is new and the cache is at `max_size`, evict to make room, in this order:
  1. If any stored entry is already expired, remove the expired entry that expires soonest, and count it in `stats()["expirations"]` (not evictions).
  2. Otherwise remove the least-recently-used entry and count it in `stats()["evictions"]`.

### `get(key, default=None)`
- Live hit: returns the value, marks key most-recently-used, increments `hits`.
- Missing key: returns `default`, increments `misses`.
- Expired key: removes the entry, increments `expirations` AND `misses` (an expired entry is a miss), returns `default`.

### `delete(key) -> bool`
- Removes the entry if present (live or expired) and returns `True`; returns `False` if absent. Never touches stats.

### `purge() -> int`
- Removes every expired entry, incrementing `expirations` for each. Returns the number removed.

### `__len__`
- Number of LIVE (unexpired) entries, without removing anything and without touching stats.

### `__contains__`
- `True` only for live entries. Must NOT touch stats and must NOT change recency order.

### `stats() -> dict`
- Returns `{"hits": int, "misses": int, "evictions": int, "expirations": int}` (a fresh dict each call).

## Semantics

- "Recently used" is updated by: `set` (new or overwrite) and a live-hit `get`. Nothing else.
- An entry expires when `clock() >= stored_expiry` (boundary counts as expired).
- Expiry is lazy: nothing is removed until a `get` on the expired key, a `purge()`, or the `set` eviction path above.
