"""Path helpers for run artifacts."""

from pathlib import Path


def ensure_parent(path):
    """Create the parent directory of *path*; returns the Path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def with_suffix_stamped(path, stamp):
    """`report.csv` + `2024w07` -> `report.2024w07.csv`."""
    target = Path(path)
    return target.with_name(f"{target.stem}.{stamp}{target.suffix}")
