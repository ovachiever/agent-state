"""Hidden verifier for feature-dep-graph. Usage: verify.py <workspace>"""

import importlib.util
import json
import sys
from pathlib import Path


def load_cls(ws: Path):
    spec = importlib.util.spec_from_file_location("depgraph", ws / "depgraph.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DepGraph


def main():
    checks = {}
    try:
        ws = Path(sys.argv[1])
        DepGraph = load_cls(ws)
    except Exception as e:
        print(json.dumps({"score": 0.0, "checks": {"imports": False}, "notes": str(e)[:200]}))
        return

    def check(name, fn):
        try:
            checks[name] = bool(fn())
        except Exception:
            checks[name] = False

    def add_errors():
        g = DepGraph()
        g.add_node("a")
        for bad in (
            lambda: g.add_node("a"),                                # duplicate node
            lambda: g.add_node("b", lambda x: x, ["ghost"]),        # unknown dep
            lambda: g.add_node("c", lambda x: x, ["c"]),            # self dep (unknown at add time)
            lambda: g.add_node("d", None, ["a"]),                   # source with deps
            lambda: g.add_node("e", lambda x, y: x + y, ["a", "a"]),  # duplicate deps
        ):
            try:
                bad()
                return False
            except ValueError:
                pass
        return True

    check("add_errors", add_errors)

    def add_reject_atomic():
        g = DepGraph()
        g.add_node("a")
        g.set_value("a", 1)
        try:
            g.add_node("z", lambda x, y: x + y, ["a", "ghost"])
            return False
        except ValueError:
            pass
        g.delete("a")            # must succeed: no phantom dependent from the failed add
        g.add_node("a")
        g.set_value("a", 2)
        g.add_node("z", lambda x: x * 10, ["a"])  # must succeed: z was never registered
        return g.get("z") == 20

    check("add_reject_atomic", add_reject_atomic)

    def source_basic():
        g = DepGraph()
        g.add_node("s")
        g.set_value("s", 5)
        if g.get("s") != 5:
            return False
        g.set_value("s", 7)
        return g.get("s") == 7 and g.recompute_count("s") == 0

    check("source_basic", source_basic)

    def computed_basic():
        g = DepGraph()
        g.add_node("a")
        g.add_node("b")
        g.set_value("a", 10)
        g.set_value("b", 3)
        g.add_node("diff", lambda x, y: x - y, ["a", "b"])  # arg order must match deps order
        return g.get("diff") == 7 and g.recompute_count("diff") == 1

    check("computed_basic", computed_basic)

    def unknown_keyerror():
        g = DepGraph()
        g.add_node("a")
        for op in (
            lambda: g.get("ghost"),
            lambda: g.set_value("ghost", 1),
            lambda: g.delete("ghost"),
            lambda: g.recompute_count("ghost"),
            lambda: g.set_deps("ghost", []),
        ):
            try:
                op()
                return False
            except KeyError:
                pass
            except Exception:
                return False
        return True

    check("unknown_name_keyerror", unknown_keyerror)

    def set_value_computed_rejected():
        g = DepGraph()
        g.add_node("s")
        g.set_value("s", 1)
        g.add_node("c", lambda x: x + 1, ["s"])
        if g.get("c") != 2:
            return False
        try:
            g.set_value("c", 99)
            return False
        except ValueError:
            pass
        return g.get("c") == 2 and g.recompute_count("c") == 1

    check("set_value_computed_rejected", set_value_computed_rejected)

    def unset_source():
        g = DepGraph()
        calls = []
        g.add_node("s")
        g.add_node("c", lambda x: calls.append("c") or x + 1, ["s"])
        try:
            g.get("s")
            return False
        except ValueError:
            pass
        try:
            g.get("c")
            return False
        except ValueError:
            pass
        if calls or g.recompute_count("c") != 0:
            return False
        g.set_value("s", 1)
        return g.get("c") == 2 and calls == ["c"]

    check("unset_source", unset_source)

    def memoization():
        g = DepGraph()
        g.add_node("s")
        g.set_value("s", 4)
        g.add_node("b", lambda x: x * 2, ["s"])
        g.add_node("c", lambda x: x + 1, ["b"])
        if g.get("c") != 9:
            return False
        g.get("c")
        g.get("c")
        g.get("b")
        return g.recompute_count("b") == 1 and g.recompute_count("c") == 1

    check("memoization", memoization)

    def dirty_propagation():
        g = DepGraph()
        g.add_node("s")
        g.set_value("s", 1)
        g.add_node("b", lambda x: x + 1, ["s"])
        g.add_node("c", lambda x: x * 10, ["b"])
        if g.get("c") != 20:
            return False
        g.set_value("s", 5)
        return g.get("c") == 60 and g.recompute_count("b") == 2 and g.recompute_count("c") == 2

    check("dirty_propagation", dirty_propagation)

    def laziness():
        g = DepGraph()
        g.add_node("s")
        g.set_value("s", 1)
        g.add_node("left", lambda x: x + 1, ["s"])
        g.add_node("right", lambda x: x - 1, ["s"])
        g.get("left")
        if g.recompute_count("right") != 0:
            return False
        g.set_value("s", 10)
        g.set_value("s", 20)
        g.get("left")
        if g.recompute_count("right") != 0 or g.recompute_count("left") != 2:
            return False
        # right recomputes once, with the latest value, despite missing two updates
        return g.get("right") == 19 and g.recompute_count("right") == 1

    check("laziness", laziness)

    def diamond_once():
        g = DepGraph()
        g.add_node("a")
        g.set_value("a", 1)
        g.add_node("b", lambda x: x + 1, ["a"])
        g.add_node("c", lambda x: x + 2, ["a"])
        g.add_node("d", lambda x, y: x * 100 + y, ["b", "c"])
        if g.get("d") != 203:
            return False
        g.set_value("a", 5)
        if g.get("d") != 607:
            return False
        return (
            g.recompute_count("b") == 2
            and g.recompute_count("c") == 2
            and g.recompute_count("d") == 2
        )

    check("diamond_once", diamond_once)

    def topo_order():
        g = DepGraph()
        calls = []

        def fn(name, f):
            def wrapped(*args):
                calls.append(name)
                return f(*args)

            return wrapped

        g.add_node("s")
        g.set_value("s", 10)
        g.add_node("x", fn("x", lambda v: v + 1), ["s"])
        g.add_node("y", fn("y", lambda v: v * 2), ["x"])
        g.add_node("z", fn("z", lambda v: v + 3), ["y"])
        if g.get("z") != 25 or calls != ["x", "y", "z"]:
            return False
        calls.clear()
        g.set_value("s", 20)
        return g.get("z") == 45 and calls == ["x", "y", "z"]

    check("topo_order", topo_order)

    def no_value_cutoff():
        g = DepGraph()
        g.add_node("s")
        g.set_value("s", 1)
        g.add_node("const", lambda x: 42, ["s"])
        g.add_node("sink", lambda x: x, ["const"])
        g.get("sink")
        g.set_value("s", 1)  # same value: must still dirty everything
        g.get("sink")
        if g.recompute_count("const") != 2 or g.recompute_count("sink") != 2:
            return False
        g.set_value("s", 2)  # const recomputes to the same 42: sink must still recompute
        g.get("sink")
        return g.recompute_count("const") == 3 and g.recompute_count("sink") == 3

    check("no_value_cutoff", no_value_cutoff)

    def cycle_rejected():
        g = DepGraph()
        g.add_node("s")
        g.set_value("s", 1)
        g.add_node("b", lambda x: x + 1, ["s"])
        g.add_node("c", lambda x: x * 2, ["b"])
        g.add_node("d", lambda x: x - 1, ["c"])
        for bad in (
            lambda: g.set_deps("b", ["b"]),
            lambda: g.set_deps("b", ["c"]),
            lambda: g.set_deps("b", ["s", "d"]),
        ):
            try:
                bad()
                return False
            except ValueError:
                pass
        return True

    check("cycle_rejected", cycle_rejected)

    def cycle_reject_atomic():
        g = DepGraph()
        g.add_node("s")
        g.set_value("s", 1)
        g.add_node("b", lambda x: x + 1, ["s"])
        g.add_node("c", lambda x: x * 2, ["b"])
        if g.get("c") != 4:
            return False
        try:
            g.set_deps("b", ["c"])
            return False
        except ValueError:
            pass
        # graph unchanged: nothing dirtied, wiring intact
        if g.get("c") != 4 or g.recompute_count("b") != 1 or g.recompute_count("c") != 1:
            return False
        g.set_value("s", 3)
        return g.get("c") == 8 and g.recompute_count("b") == 2

    check("cycle_reject_atomic", cycle_reject_atomic)

    def set_deps_semantics():
        g = DepGraph()
        g.add_node("s1")
        g.set_value("s1", 1)
        g.add_node("s2")
        g.set_value("s2", 100)
        g.add_node("b", lambda x: x + 1, ["s1"])
        g.add_node("sink", lambda x: x * 2, ["b"])
        if g.get("sink") != 4:
            return False
        try:
            g.set_deps("s1", [])  # source: rejected
            return False
        except ValueError:
            pass
        try:
            g.set_deps("b", ["ghost"])  # unknown dep: rejected, graph untouched
            return False
        except ValueError:
            pass
        if g.recompute_count("b") != 1 or g.get("sink") != 4:
            return False
        g.set_deps("b", ["s2"])
        if g.get("sink") != 202:
            return False
        if g.recompute_count("b") != 2 or g.recompute_count("sink") != 2:
            return False
        g.delete("s1")  # b no longer depends on s1, so s1 is deletable
        return g.get("sink") == 202

    check("set_deps_semantics", set_deps_semantics)

    def delete_semantics():
        g = DepGraph()
        g.add_node("s")
        g.set_value("s", 1)
        g.add_node("b", lambda x: x + 1, ["s"])
        try:
            g.delete("s")  # has a dependent
            return False
        except ValueError:
            pass
        if g.get("b") != 2:  # graph still functional after the rejected delete
            return False
        g.delete("b")
        try:
            g.get("b")
            return False
        except KeyError:
            pass
        g.delete("s")  # b gone, so s has no dependents
        g.add_node("b")  # name reusable, now as a fresh source
        g.set_value("b", 9)
        return g.get("b") == 9 and g.recompute_count("b") == 0

    check("delete_semantics", delete_semantics)

    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"score": 0.0, "checks": {}}))
