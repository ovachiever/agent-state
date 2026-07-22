"""Basic sanity test. Passing this alone does NOT mean the spec is met."""

from scheduler import Scheduler


def test_basic():
    s = Scheduler()
    log = []
    a = s.submit(lambda: log.append("a") or "ra", priority=1)
    b = s.submit(lambda: log.append("b") or "rb", priority=0)
    s.add_done_callback(a, lambda tid, res: log.append(("cb", res)))
    n = s.run(10)
    assert n == 2
    assert log == ["b", "a", ("cb", "ra")]
    assert s.state(a) == "done" and s.result(a) == "ra"
    assert s.state(b) == "done" and s.result(b) == "rb"


if __name__ == "__main__":
    test_basic()
    print("ok")
