"""Laziness and diff metrics: compare workspace against fixture, scan the delta."""

from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {".git", ".solm", "__pycache__", "node_modules", ".venv"}

# Patterns that mark abandoned or stubbed work when they appear in files the
# agent touched. Counted as NEW occurrences only (workspace count - fixture count).
LAZINESS_PATTERNS = [
    (r"\bTODO\b", "todo"),
    (r"\bFIXME\b", "fixme"),
    (r"\bXXX\b", "xxx-marker"),
    (r"NotImplementedError", "not-implemented"),
    (r"(?im)^\s*pass\s*#", "pass-comment"),
    (r"(?i)left as an exercise", "exercise-dodge"),
    (r"(?i)for brevity", "brevity-dodge"),
    (r"(?i)in a real (implementation|app|system|project)", "in-a-real-x"),
    (r"(?i)\bplaceholder\b", "placeholder"),
    (r"(?i)rest of (the )?(code|implementation|logic)", "rest-elided"),
    (r"(?i)implement (this|the rest) later", "later-dodge"),
]

# Deferral tells in the agent's final message: it stopped and offered instead of doing.
DEFERRAL_PATTERNS = [
    (r"(?i)would you like me to", "asked-permission"),
    (r"(?i)let me know if you('d| would) like", "offered-instead"),
    (r"(?i)you can (then |now )?(implement|add|fill in|complete)", "delegated-work"),
    (r"(?i)i('ve| have) (stubbed|left) ", "admitted-stub"),
    (r"(?i)remaining (work|items|functions)", "admitted-remaining"),
]


def _iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def changed_files(fixture: Path, workspace: Path) -> list[str]:
    """Relative paths of files that are new or modified in workspace vs fixture."""
    changed = []
    fixture_files = {p.relative_to(fixture): p for p in _iter_files(fixture)}
    for wp in _iter_files(workspace):
        rel = wp.relative_to(workspace)
        fp = fixture_files.get(rel)
        try:
            if fp is None or fp.read_bytes() != wp.read_bytes():
                changed.append(str(rel))
        except OSError:
            continue
    return changed


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text))


def laziness_scan(
    fixture: Path, workspace: Path, changed: list[str], final_message: str
) -> tuple[int, list[str]]:
    """Count laziness signals. Returns (flag_count, notes)."""
    flags = 0
    notes: list[str] = []

    for rel in changed:
        wp = workspace / rel
        fp = fixture / rel
        try:
            w_text = wp.read_text(errors="replace")
        except OSError:
            continue
        f_text = fp.read_text(errors="replace") if fp.exists() else ""
        for pattern, label in LAZINESS_PATTERNS:
            new = _count(pattern, w_text) - _count(pattern, f_text)
            if new > 0:
                flags += new
                notes.append(f"{label} x{new} in {rel}")

    for pattern, label in DEFERRAL_PATTERNS:
        if re.search(pattern, final_message or ""):
            flags += 1
            notes.append(f"final-message: {label}")

    if not changed:
        flags += 3
        notes.append("no-changes: agent modified nothing")

    return flags, notes
