"""Basic sanity test. Passing this alone does NOT mean the spec is met."""

from topk import TopK


def test_basic():
    t = TopK(5)
    assert t.add("a", 5.0) is True
    assert t.add("b", 9) is True
    assert t.add("c", 2) is True
    assert t.snapshot() == [["b", 9], ["a", 5.0], ["c", 2]]
    assert len(t) == 3


if __name__ == "__main__":
    test_basic()
    print("ok")
