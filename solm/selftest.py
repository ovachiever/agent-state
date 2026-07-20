"""Prove every verifier before trusting it with model runs.

For each task: the raw fixture must NOT score 1.0 (otherwise the task tests
nothing), and the committed reference solution MUST score 1.0 (otherwise the
verifier is broken or the bar is wrong).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from solm.config import load_tasks
from solm.harness import run_verifier


def _overlay(src: Path, dst: Path) -> None:
    for p in src.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)


def run_selftest(names: list[str] | None = None) -> bool:
    tasks = load_tasks(names)
    all_ok = True
    for task in tasks:
        with tempfile.TemporaryDirectory(prefix=f"solm-selftest-{task.name}-") as tmp:
            ws = Path(tmp) / "ws"
            shutil.copytree(task.fixture_dir, ws)

            fixture_score, _, fixture_err = run_verifier(task, ws)
            if not task.solution_dir.exists():
                print(f"✖ {task.name}: no solution/ directory")
                all_ok = False
                continue
            _overlay(task.solution_dir, ws)
            solution_score, checks, sol_err = run_verifier(task, ws)

        problems = []
        if fixture_score >= 0.999:
            problems.append(f"fixture already scores {fixture_score:.2f} — task tests nothing")
        if solution_score < 0.999:
            failed = [k for k, v in checks.items() if not v]
            problems.append(
                f"solution scores {solution_score:.2f} (failed: {', '.join(failed) or sol_err or fixture_err or 'unknown'})"
            )
        if problems:
            print(f"✖ {task.name}: " + "; ".join(problems))
            all_ok = False
        else:
            print(f"✔ {task.name}: fixture {fixture_score:.2f} → solution {solution_score:.2f} ({len(checks)} checks)")
    return all_ok
