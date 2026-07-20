"""Hidden verifier for bugfix-intervals. Usage: verify.py <workspace>"""

import copy
import importlib.util
import json
import sys
from pathlib import Path


def load_module(ws: Path):
    spec = importlib.util.spec_from_file_location("intervals", ws / "intervals.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ws = Path(sys.argv[1])
    checks = {}
    try:
        mod = load_module(ws)
        f = mod.merge_intervals
    except Exception as e:
        print(json.dumps({"score": 0.0, "checks": {"imports": False}, "notes": str(e)}))
        return

    def check(name, fn):
        try:
            checks[name] = bool(fn())
        except Exception:
            checks[name] = False

    check("basic_overlap", lambda: f([[1, 4], [2, 6], [8, 10]]) == [[1, 6], [8, 10]])
    check("touching_merges", lambda: f([[1, 3], [3, 5]]) == [[1, 5]])
    check("unsorted_input", lambda: f([[8, 10], [1, 4], [2, 6]]) == [[1, 6], [8, 10]])
    check("empty", lambda: f([]) == [])
    check("degenerate_points", lambda: f([[2, 2], [2, 2]]) == [[2, 2]])
    check("point_touches_interval", lambda: f([[5, 5], [1, 5]]) == [[1, 5]])
    check("floats", lambda: f([[0.5, 1.5], [1.25, 2.0]]) == [[0.5, 2.0]])
    check("single", lambda: f([[3, 7]]) == [[3, 7]])

    def input_not_mutated():
        data = [[8, 10], [1, 4], [2, 6]]
        snapshot = copy.deepcopy(data)
        f(data)
        return data == snapshot

    check("input_not_mutated", input_not_mutated)

    def no_aliasing():
        data = [[1, 4], [10, 12]]
        result = f(data)
        for r in result:
            for d in data:
                if r is d:
                    return False
        result[0][0] = -999
        return data == [[1, 4], [10, 12]]

    check("no_aliasing", no_aliasing)

    def raises(data):
        def probe():
            try:
                f(data)
            except ValueError:
                return True
            return False
        return probe

    # Invalid interval sorting FIRST and an invalid SINGLE interval are the
    # cases the buggy validate-in-loop approach misses.
    check("raises_invalid_sorts_first", raises([[0, -5], [1, 3]]))
    check("raises_invalid_single", raises([[5, 2]]))
    check("raises_invalid_last", raises([[1, 3], [9, 4]]))

    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


if __name__ == "__main__":
    main()
