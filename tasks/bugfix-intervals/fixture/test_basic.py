"""Basic sanity test. Passing this alone does NOT mean the spec is met."""

from intervals import merge_intervals


def test_basic_overlap():
    assert merge_intervals([[1, 4], [2, 6], [8, 10]]) == [[1, 6], [8, 10]]


if __name__ == "__main__":
    test_basic_overlap()
    print("ok")
