"""Event counter."""


class Counter:
    """Accumulates numeric samples.

    add(value): record a sample. Every finite numeric value is recorded,
    including zero and negatives.
    count(): number of samples recorded.
    total(): sum of recorded samples.
    """

    def __init__(self):
        self._values = []

    def add(self, value):
        self._values.append(value)

    def count(self):
        return len(self._values)

    def total(self):
        return sum(self._values)

    def stats(self):
        if not self._values:
            raise ValueError("no samples recorded")
        return {
            "min": min(self._values),
            "max": max(self._values),
            "mean": sum(self._values) / len(self._values),
        }
