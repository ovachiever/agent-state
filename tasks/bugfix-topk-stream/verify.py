"""Hidden verifier for bugfix-topk-stream. Usage: verify.py <workspace>"""

import importlib.util
import json
import sys
from pathlib import Path


def load_cls(ws: Path):
    spec = importlib.util.spec_from_file_location("topk", ws / "topk.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TopK


def main():
    checks = {}
    try:
        ws = Path(sys.argv[1])
        TopK = load_cls(ws)
    except Exception as e:
        print(json.dumps({"score": 0.0, "checks": {"imports": False}, "notes": str(e)[:200]}))
        return

    def check(name, fn):
        try:
            checks[name] = bool(fn())
        except Exception:
            checks[name] = False

    def k_validation():
        for bad in (0, -2, 2.0):
            try:
                TopK(bad)
                return False
            except ValueError:
                pass
            except Exception:
                return False
        TopK(1)
        TopK(10)
        return True

    check("k_validation", k_validation)

    def basic_order():
        t = TopK(4)
        if t.add("a", 5) is not True or t.add("b", 9) is not True or t.add("c", 2) is not True:
            return False
        return t.snapshot() == [["b", 9], ["a", 5], ["c", 2]] and len(t) == 3

    check("basic_order", basic_order)

    def capacity_exact():
        t = TopK(3)
        for item, score in (("a", 5), ("b", 1), ("c", 9)):
            if t.add(item, score) is not True:
                return False
        if t.add("d", 7) is not True:  # displaces b
            return False
        if len(t) != 3 or t.snapshot() != [["c", 9], ["d", 7], ["a", 5]]:
            return False
        if t.add("e", 0) is not False:  # worse than the worst: rejected
            return False
        return t.snapshot() == [["c", 9], ["d", 7], ["a", 5]] and len(t) == 3

    check("capacity_exact", capacity_exact)

    def k_one():
        t = TopK(1)
        if t.add("a", 5) is not True:
            return False
        if t.add("b", 3) is not False:
            return False
        if t.add("c", 9) is not True:
            return False
        return t.snapshot() == [["c", 9]] and len(t) == 1

    check("k_one", k_one)

    def tie_insertion_order():
        t = TopK(5)
        t.add("a", 7)
        t.add("b", 7)
        t.add("c", 7)
        if t.snapshot() != [["a", 7], ["b", 7], ["c", 7]]:
            return False
        t.add("d", 9)
        t.add("e", 7)
        return t.snapshot() == [["d", 9], ["a", 7], ["b", 7], ["c", 7], ["e", 7]]

    check("tie_insertion_order", tie_insertion_order)

    def tie_boundary_incumbent():
        t = TopK(2)
        t.add("a", 9)
        t.add("b", 5)
        if t.add("c", 5) is not False:  # ties the worst: incumbent stays
            return False
        return t.snapshot() == [["a", 9], ["b", 5]] and len(t) == 2

    check("tie_boundary_incumbent", tie_boundary_incumbent)

    def return_accounting():
        t = TopK(2)
        if t.add("a", 4) is not True:
            return False
        if t.add("b", 6) is not True:
            return False
        if t.add("c", 4) is not False:  # ties worst incumbent a
            return False
        if t.add("d", 5) is not True:  # strictly beats a: admitted
            return False
        if t.add("e", 5) is not False:  # ties new worst d
            return False
        return t.snapshot() == [["b", 6], ["d", 5]]

    check("return_accounting", return_accounting)

    def snapshot_shape():
        t = TopK(3)
        if t.snapshot() != []:
            return False
        t.add("a", 1)
        t.add("b", 2)
        snap = t.snapshot()
        return (
            isinstance(snap, list)
            and all(isinstance(p, list) and len(p) == 2 for p in snap)
            and snap == [["b", 2], ["a", 1]]
        )

    check("snapshot_shape", snapshot_shape)

    def snapshot_tracker_independent():
        t = TopK(3)
        t.add("a", 5)
        t.add("b", 3)
        snap = t.snapshot()
        snap[0][1] = -999
        snap.append(["junk", 1])
        if t.snapshot() != [["a", 5], ["b", 3]]:
            return False
        snap2 = t.snapshot()
        snap2.clear()
        return t.snapshot() == [["a", 5], ["b", 3]] and len(t) == 2

    check("snapshot_tracker_independent", snapshot_tracker_independent)

    def snapshot_fresh_pairs():
        t = TopK(3)
        t.add("a", 5)
        s1 = t.snapshot()
        s2 = t.snapshot()
        s1[0][0] = "mutated"
        if s2 != [["a", 5]]:
            return False
        t.add("b", 9)  # must not alter the previously returned snapshot
        return s2 == [["a", 5]] and t.snapshot() == [["b", 9], ["a", 5]]

    check("snapshot_fresh_pairs", snapshot_fresh_pairs)

    def duplicate_items():
        t = TopK(3)
        t.add("x", 5)
        t.add("x", 9)
        t.add("x", 5)
        return t.snapshot() == [["x", 9], ["x", 5], ["x", 5]] and len(t) == 3

    check("duplicate_items", duplicate_items)

    def mixed_number_scores():
        t = TopK(4)
        t.add("a", -1.5)
        t.add("b", 0)
        t.add("c", -7)
        return t.snapshot() == [["b", 0], ["a", -1.5], ["c", -7]]

    check("mixed_number_scores", mixed_number_scores)

    def churn_integration():
        t = TopK(3)
        stream = [
            ("a", 5, True),
            ("b", 5, True),   # tie: ranks after a
            ("c", 7, True),
            ("d", 5, False),  # ties worst (b): rejected
            ("e", 6, True),   # beats worst: evicts b (lowest-ranked of the 5s)
            ("f", 6, True),   # beats worst (a=5): admitted, ranks after e
            ("g", 6, False),  # ties worst (f): rejected
        ]
        for item, score, expected in stream:
            if t.add(item, score) is not expected:
                return False
        return t.snapshot() == [["c", 7], ["e", 6], ["f", 6]] and len(t) == 3

    check("churn_integration", churn_integration)

    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"score": 0.0, "checks": {}}))
