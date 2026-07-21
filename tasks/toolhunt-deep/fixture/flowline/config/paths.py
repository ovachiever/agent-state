"""Well-known filesystem locations for pipeline state."""

from pathlib import Path


def state_dir(base=None):
    """Directory for run bookkeeping; created on first use."""
    root = Path(base) if base else Path.home() / ".flowline"
    root.mkdir(parents=True, exist_ok=True)
    return root


def runs_dir(base=None):
    """Subdirectory holding one folder per pipeline run."""
    return state_dir(base) / "runs"
