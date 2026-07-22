"""Hidden verifier for bugfix-scheduler. Usage: verify.py <workspace>"""

import importlib.util
import json
import sys
from pathlib import Path

ALL_CHECKS = [
    "basic_flow", "priority_ordering", "ids_states_errors",
    "empty_run_negative_budget", "pending_snapshot", "fifo_equal_priority",
    "fifo_mixed_priorities", "requeue_goes_to_back", "requeue_alternation",
    "requeue_state_and_callbacks", "run_zero_budget", "budget_exact",
    "budget_counts_requeue", "cancel_discards_registrations",
    "cancel_never_fires", "cancel_errors", "submit_during_callback_same_run",
    "submit_during_fn_visible", "interaction_full_trace",
    "interaction_budget_boundary", "interaction_cancel_reentrant",
]


def main():
    checks = {name: False for name in ALL_CHECKS}
    try:
        run_checks(checks)
    except Exception:
        pass
    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


def run_checks(checks):
    ws = Path(sys.argv[1]).resolve()
    spec = importlib.util.spec_from_file_location("scheduler", ws / "scheduler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    S = mod.Scheduler

    def check(name, fn):
        try:
            checks[name] = bool(fn())
        except Exception:
            checks[name] = False

    def raises(fn, exc):
        try:
            fn()
        except exc:
            return True
        except Exception:
            return False
        return False

    def mkfn(log, name, rets=()):
        queue = list(rets)

        def fn():
            log.append(name)
            return queue.pop(0) if queue else name

        return fn

    # -- basics (spec surface) ------------------------------------------

    def basic_flow():
        s, log = S(), []
        a = s.submit(mkfn(log, "a", ["ra"]), priority=1)
        b = s.submit(mkfn(log, "b", ["rb"]), priority=0)
        s.add_done_callback(a, lambda t, r: log.append(("cb", t, r)))
        n = s.run(10)
        return (
            n == 2
            and log == ["b", "a", ("cb", a, "ra")]
            and s.state(a) == "done" and s.result(a) == "ra"
            and s.state(b) == "done" and s.result(b) == "rb"
        )

    check("basic_flow", basic_flow)

    def priority_ordering():
        s, log = S(), []
        s.submit(mkfn(log, "p5"), priority=5)
        s.submit(mkfn(log, "p1"), priority=1)
        s.submit(mkfn(log, "p3"), priority=3)
        return s.run(10) == 3 and log == ["p1", "p3", "p5"]

    check("priority_ordering", priority_ordering)

    def ids_states_errors():
        s, log = S(), []
        t1 = s.submit(mkfn(log, "t1"))
        t2 = s.submit(mkfn(log, "t2"))
        t3 = s.submit(mkfn(log, "t3"))
        if (t1, t2, t3) != (1, 2, 3):
            return False
        if s.state(t1) != "ready":
            return False
        return (
            raises(lambda: s.state(99), KeyError)
            and raises(lambda: s.result(t1), ValueError)
            and raises(lambda: s.result(99), KeyError)
            and raises(lambda: s.cancel(99), KeyError)
            and raises(lambda: s.add_done_callback(99, lambda t, r: None), KeyError)
            and raises(lambda: s.callback_count(99), KeyError)
        )

    check("ids_states_errors", ids_states_errors)

    def empty_run_negative_budget():
        s, log = S(), []
        if s.run(5) != 0:
            return False
        if not raises(lambda: s.run(-1), ValueError):
            return False
        s.submit(mkfn(log, "x"))
        return s.run(5) == 1 and log == ["x"]

    check("empty_run_negative_budget", empty_run_negative_budget)

    def pending_snapshot():
        s, log = S(), []
        x = s.submit(mkfn(log, "x"), priority=2)
        y = s.submit(mkfn(log, "y"), priority=1)
        got = s.pending()
        if got != [y, x]:
            return False
        got.append(999)
        return s.pending() == [y, x]

    check("pending_snapshot", pending_snapshot)

    # -- FIFO tie-break --------------------------------------------------

    def fifo_equal_priority():
        s, log = S(), []
        a = s.submit(mkfn(log, "a"), priority=5)
        b = s.submit(mkfn(log, "b"), priority=5)
        c = s.submit(mkfn(log, "c"), priority=5)
        return s.pending() == [a, b, c] and s.run(10) == 3 and log == ["a", "b", "c"]

    check("fifo_equal_priority", fifo_equal_priority)

    def fifo_mixed_priorities():
        s, log = S(), []
        x = s.submit(mkfn(log, "x"), priority=1)
        y = s.submit(mkfn(log, "y"), priority=0)
        z = s.submit(mkfn(log, "z"), priority=1)
        w = s.submit(mkfn(log, "w"), priority=0)
        return s.pending() == [y, w, x, z] and s.run(10) == 4 and log == ["y", "w", "x", "z"]

    check("fifo_mixed_priorities", fifo_mixed_priorities)

    # -- requeue ---------------------------------------------------------

    def requeue_goes_to_back():
        s, log = S(), []
        a = s.submit(mkfn(log, "a", ["again"]))
        b = s.submit(mkfn(log, "b"))
        return (
            s.run(10) == 3
            and log == ["a", "b", "a"]
            and s.state(a) == "done" and s.state(b) == "done"
        )

    check("requeue_goes_to_back", requeue_goes_to_back)

    def requeue_alternation():
        s, log = S(), []
        s.submit(mkfn(log, "a", ["again", "again"]))
        s.submit(mkfn(log, "b", ["again"]))
        return s.run(10) == 5 and log == ["a", "b", "a", "b", "a"]

    check("requeue_alternation", requeue_alternation)

    def requeue_state_and_callbacks():
        s, log, cbs = S(), [], []
        a = s.submit(mkfn(log, "a", ["again"]))
        s.add_done_callback(a, lambda t, r: cbs.append((t, r)))
        if s.run(1) != 1 or log != ["a"]:
            return False
        if s.state(a) != "ready" or s.pending() != [a]:
            return False
        if s.callback_count(a) != 1 or cbs:
            return False
        if s.run(10) != 1:
            return False
        return cbs == [(a, "a")] and s.callback_count(a) == 0 and s.result(a) == "a"

    check("requeue_state_and_callbacks", requeue_state_and_callbacks)

    # -- budget ----------------------------------------------------------

    def run_zero_budget():
        s, log = S(), []
        t1 = s.submit(mkfn(log, "t1"), priority=1)
        t2 = s.submit(mkfn(log, "t2"), priority=2)
        return s.run(0) == 0 and log == [] and s.pending() == [t1, t2]

    check("run_zero_budget", run_zero_budget)

    def budget_exact():
        s, log = S(), []
        ids = [s.submit(mkfn(log, f"t{i}"), priority=i) for i in range(1, 6)]
        if s.run(2) != 2 or log != ["t1", "t2"]:
            return False
        if s.pending() != ids[2:]:
            return False
        return s.run(10) == 3 and log == ["t1", "t2", "t3", "t4", "t5"]

    check("budget_exact", budget_exact)

    def budget_counts_requeue():
        s, log = S(), []
        s.submit(mkfn(log, "a", ["again"]), priority=1)
        b = s.submit(mkfn(log, "b"), priority=2)
        c = s.submit(mkfn(log, "c"), priority=3)
        return s.run(2) == 2 and log == ["a", "a"] and s.pending() == [b, c]

    check("budget_counts_requeue", budget_counts_requeue)

    # -- cancellation ----------------------------------------------------

    def cancel_discards_registrations():
        s, log = S(), []
        a = s.submit(mkfn(log, "a"), priority=1)
        b = s.submit(mkfn(log, "b"), priority=2)
        s.add_done_callback(a, lambda t, r: log.append(("cb", t, r)))
        s.cancel(a)
        return s.callback_count(a) == 0 and s.state(a) == "cancelled" and s.pending() == [b]

    check("cancel_discards_registrations", cancel_discards_registrations)

    def cancel_never_fires():
        s, log, cbs = S(), [], []
        a = s.submit(mkfn(log, "a"), priority=1)
        s.submit(mkfn(log, "b"), priority=2)
        s.add_done_callback(a, lambda t, r: cbs.append((t, r)))
        s.cancel(a)
        return s.run(10) == 1 and log == ["b"] and cbs == [] and s.callback_count(a) == 0

    check("cancel_never_fires", cancel_never_fires)

    def cancel_errors():
        s, log = S(), []
        a = s.submit(mkfn(log, "a"))
        b = s.submit(mkfn(log, "b"))
        s.cancel(b)
        s.run(10)
        return (
            raises(lambda: s.cancel(a), ValueError)          # done
            and raises(lambda: s.cancel(b), ValueError)      # already cancelled
            and raises(lambda: s.add_done_callback(a, print), ValueError)
            and raises(lambda: s.add_done_callback(b, print), ValueError)
            and raises(lambda: s.result(b), ValueError)
        )

    check("cancel_errors", cancel_errors)

    # -- reentrancy ------------------------------------------------------

    def submit_during_callback_same_run():
        s, log = S(), []
        holder = {}

        def cb(t, r):
            holder["x"] = s.submit(mkfn(log, "x", ["rx"]), priority=9)

        a = s.submit(mkfn(log, "a"), priority=1)
        s.submit(mkfn(log, "b"), priority=2)
        s.add_done_callback(a, cb)
        n = s.run(10)
        return (
            n == 3
            and log == ["a", "b", "x"]
            and s.state(holder["x"]) == "done"
            and s.result(holder["x"]) == "rx"
        )

    check("submit_during_callback_same_run", submit_during_callback_same_run)

    def submit_during_fn_visible():
        s, log = S(), []
        holder = {}

        def fn_a():
            log.append("a")
            holder["x"] = s.submit(mkfn(log, "x"), priority=9)
            return "done-a"

        s.submit(fn_a, priority=1)
        if s.run(1) != 1 or log != ["a"]:
            return False
        x = holder["x"]
        if s.pending() != [x] or s.state(x) != "ready":
            return False
        return s.run(10) == 1 and log == ["a", "x"]

    check("submit_during_fn_visible", submit_during_fn_visible)

    # -- interactions (all five defects must be gone) --------------------

    def interaction_full_trace():
        s, log, cbs = S(), [], []
        holder = {}

        t1 = s.submit(mkfn(log, "t1", ["again", "r1"]), priority=0)
        t2 = s.submit(mkfn(log, "t2", ["r2"]), priority=0)
        t3 = s.submit(mkfn(log, "t3", ["r3"]), priority=1)
        t4 = s.submit(mkfn(log, "t4"), priority=0)

        s.add_done_callback(t1, lambda t, r: cbs.append(("cb1", t, r)))

        def cb2(t, r):
            cbs.append(("cb2", t, r))
            holder["t5"] = s.submit(mkfn(log, "t5", ["r5"]), priority=0)

        s.add_done_callback(t2, cb2)
        s.add_done_callback(t4, lambda t, r: cbs.append(("cb4", t, r)))
        s.cancel(t4)
        if s.callback_count(t4) != 0:
            return False

        n = s.run(4)
        t5 = holder.get("t5")
        if n != 4 or log != ["t1", "t2", "t1", "t5"]:
            return False
        if cbs != [("cb2", t2, "r2"), ("cb1", t1, "r1")]:
            return False
        if s.pending() != [t3]:
            return False
        states = [s.state(t) for t in (t1, t2, t3, t4, t5)]
        if states != ["done", "done", "ready", "cancelled", "done"]:
            return False
        if s.result(t5) != "r5":
            return False
        return s.run(10) == 1 and log[-1] == "t3"

    check("interaction_full_trace", interaction_full_trace)

    def interaction_budget_boundary():
        s, log, cbs = S(), [], []
        holder = {}

        a = s.submit(mkfn(log, "a", ["again", "again"]), priority=0)
        b = s.submit(mkfn(log, "b"), priority=0)
        c = s.submit(mkfn(log, "c"), priority=0)

        def cba(t, r):
            cbs.append(("cba", t, r))
            holder["e"] = s.submit(mkfn(log, "e"), priority=0)

        s.add_done_callback(a, cba)
        s.add_done_callback(b, lambda t, r: cbs.append(("cbb", t, r)))
        s.cancel(b)

        if s.run(4) != 4 or log != ["a", "c", "a", "a"]:
            return False
        e = holder.get("e")
        if cbs != [("cba", a, "a")] or s.pending() != [e] or s.state(e) != "ready":
            return False
        if s.run(0) != 0 or s.pending() != [e]:
            return False
        return s.run(10) == 1 and log[-1] == "e" and s.state(e) == "done"

    check("interaction_budget_boundary", interaction_budget_boundary)

    def interaction_cancel_reentrant():
        s, log, cbs = S(), [], []
        holder = {}
        ids = {}

        def fn_t1():
            log.append("t1")
            if "cancelled" not in holder:
                holder["cancelled"] = True
                s.cancel(ids["t2"])
                return "again"
            holder["x"] = s.submit(mkfn(log, "x"), priority=0)
            return "f"

        ids["t1"] = s.submit(fn_t1, priority=0)
        ids["t2"] = s.submit(mkfn(log, "t2"), priority=0)
        t3 = s.submit(mkfn(log, "t3"), priority=0)
        t4 = s.submit(mkfn(log, "t4"), priority=9)
        s.add_done_callback(ids["t2"], lambda t, r: cbs.append(("cb2", t, r)))

        if s.run(4) != 4 or log != ["t1", "t3", "t1", "x"]:
            return False
        x = holder.get("x")
        if cbs != [] or s.callback_count(ids["t2"]) != 0:
            return False
        if s.state(t4) != "ready" or s.pending() != [t4]:
            return False
        return (
            s.state(x) == "done"
            and s.result(ids["t1"]) == "f"
            and s.state(ids["t2"]) == "cancelled"
            and s.state(t3) == "done"
        )

    check("interaction_cancel_reentrant", interaction_cancel_reentrant)


if __name__ == "__main__":
    main()
