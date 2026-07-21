"""Manual stopwatch used by the pipeline driver for stage timing."""


class Stopwatch:
    """Accumulates externally supplied tick durations (no wall-clock)."""

    def __init__(self):
        self.laps = []

    def record(self, seconds):
        self.laps.append(float(seconds))
        return self

    def total(self):
        return round(sum(self.laps), 6)
