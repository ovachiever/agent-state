"""Interval utilities."""


def merge_intervals(intervals):
    """Merge overlapping or touching intervals.

    Spec:
    - `intervals` is a list of [start, end] pairs (ints or floats), possibly
      unsorted. Degenerate points where start == end are valid.
    - Overlapping intervals merge; touching intervals also merge:
      [1, 3] and [3, 5] -> [1, 5].
    - Returns a new list of [start, end] pairs sorted by start.
    - The input list must not be mutated, and no list object in the input may
      be aliased by the result (the result must be fully independent copies).
    - Empty input returns [].
    - Raises ValueError if any interval has start > end (checked for every
      interval, before any merging happens).
    """
    for start, end in intervals:
        if start > end:
            raise ValueError(f"invalid interval: [{start}, {end}]")
    if not intervals:
        return []
    ordered = sorted([list(pair) for pair in intervals])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
