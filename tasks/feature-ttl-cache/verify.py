"""Hidden verifier for feature-ttl-cache. Usage: verify.py <workspace>"""

import importlib.util
import json
import sys
from pathlib import Path


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def load_cls(ws: Path):
    spec = importlib.util.spec_from_file_location("ttl_cache", ws / "ttl_cache.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TTLCache


def main():
    ws = Path(sys.argv[1])
    checks = {}
    try:
        TTLCache = load_cls(ws)
    except Exception as e:
        print(json.dumps({"score": 0.0, "checks": {"imports": False}, "notes": str(e)}))
        return

    def check(name, fn):
        try:
            checks[name] = bool(fn())
        except Exception:
            checks[name] = False

    def fresh(max_size=3, ttl=10.0):
        clock = FakeClock()
        return TTLCache(max_size, ttl, clock=clock), clock

    def ctor_validation():
        for bad in (lambda: TTLCache(0, 10.0), lambda: TTLCache(3, 0)):
            try:
                bad()
                return False
            except ValueError:
                pass
        return True

    check("ctor_validation", ctor_validation)

    def basic():
        c, _ = fresh()
        c.set("a", 1)
        return c.get("a") == 1 and c.get("nope", "dflt") == "dflt"

    check("basic_set_get", basic)

    def expiry_boundary():
        c, clock = fresh(ttl=10.0)
        c.set("a", 1)
        clock.t += 9.999
        if c.get("a") != 1:
            return False
        c.set("b", 2)
        clock.t += 10.0  # b now exactly at expiry: expired
        return c.get("b", "gone") == "gone"

    check("expiry_boundary", expiry_boundary)

    def per_key_ttl():
        c, clock = fresh(ttl=10.0)
        c.set("short", 1, ttl=2.0)
        c.set("long", 2, ttl=50.0)
        clock.t += 5.0
        return c.get("short", None) is None and c.get("long") == 2

    check("per_key_ttl", per_key_ttl)

    def ttl_validation():
        c, _ = fresh()
        try:
            c.set("a", 1, ttl=0)
            return False
        except ValueError:
            return True

    check("ttl_validation", ttl_validation)

    def lru_eviction():
        c, _ = fresh(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")            # refreshes a; LRU is now b
        c.set("c", 3)         # evicts b
        return ("b" not in c) and ("a" in c) and ("c" in c) and c.stats()["evictions"] == 1

    check("lru_eviction_respects_get", lru_eviction)

    def overwrite_refreshes():
        c, _ = fresh(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("a", 99)        # overwrite: a becomes MRU, no eviction
        if c.stats()["evictions"] != 0:
            return False
        c.set("c", 3)         # evicts b (LRU), not a
        return c.get("a") == 99 and "b" not in c

    check("overwrite_refreshes", overwrite_refreshes)

    def expired_evicted_first():
        c, clock = fresh(max_size=3, ttl=100.0)
        c.set("later", 1, ttl=20.0)
        c.set("soonest", 2, ttl=5.0)
        c.set("live", 3, ttl=100.0)
        clock.t += 30.0       # 'later' and 'soonest' both expired; 'live' alive
        c.set("new", 4)       # must remove 'soonest' (expires earliest), count as expiration
        st = c.stats()
        if st["evictions"] != 0 or st["expirations"] != 1:
            return False
        # 'later' must still be stored (expired but unpurged): delete returns True
        return c.delete("later") is True and "live" in c and "new" in c

    check("expired_evicted_before_lru", expired_evicted_first)

    def stats_accounting():
        c, clock = fresh(ttl=10.0)
        c.set("a", 1)
        c.get("a")            # hit
        c.get("zzz")          # miss
        clock.t += 20.0       # a expired
        c.get("a")            # expired: miss + expiration
        st = c.stats()
        return st == {"hits": 1, "misses": 2, "evictions": 0, "expirations": 1}

    check("stats_accounting", stats_accounting)

    def len_live_only():
        c, clock = fresh(max_size=5, ttl=10.0)
        c.set("a", 1)
        c.set("b", 2, ttl=2.0)
        clock.t += 5.0
        before = c.stats()
        n = len(c)
        return n == 1 and c.stats() == before and c.delete("b") is True

    check("len_live_only", len_live_only)

    def contains_neutral():
        c, _ = fresh(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        before = c.stats()
        _ = "a" in c          # must not refresh recency or touch stats
        if c.stats() != before:
            return False
        c.set("c", 3)         # LRU must still be a
        return "a" not in c and "b" in c

    check("contains_is_neutral", contains_neutral)

    def delete_semantics():
        c, _ = fresh()
        c.set("a", 1)
        before = c.stats()
        return c.delete("a") is True and c.delete("a") is False and c.stats() == before

    check("delete_semantics", delete_semantics)

    def purge_semantics():
        c, clock = fresh(max_size=5, ttl=10.0)
        c.set("a", 1, ttl=2.0)
        c.set("b", 2, ttl=3.0)
        c.set("c", 3, ttl=100.0)
        clock.t += 5.0
        n = c.purge()
        st = c.stats()
        return n == 2 and st["expirations"] == 2 and len(c) == 1 and "c" in c

    check("purge_semantics", purge_semantics)

    def fresh_stats_dict():
        c, _ = fresh()
        s1 = c.stats()
        s1["hits"] = 999
        return c.stats()["hits"] == 0

    check("fresh_stats_dict", fresh_stats_dict)

    def clock_injected():
        # If the implementation reads real time instead of the injected clock,
        # entries never expire under a frozen clock advanced manually.
        c, clock = fresh(ttl=1.0)
        c.set("a", 1)
        clock.t += 2.0
        return "a" not in c

    check("clock_injected", clock_injected)

    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


if __name__ == "__main__":
    main()
