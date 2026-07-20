"""Load config.toml and task definitions."""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
DATA_DIR = REPO_ROOT / "data"
REPORTS_DIR = REPO_ROOT / "reports"
LOGS_DIR = REPO_ROOT / "logs"
WORKSPACE_ROOT = Path.home() / ".cache" / "state-of-llm" / "workspaces"

DIMENSIONS = ["intelligence", "tool_use", "diligence", "plot"]

FALLBACK_BINS = {
    "claude": [
        "/Users/erik/.nvm/versions/node/v22.16.0/bin/claude",
        str(Path.home() / ".claude" / "local" / "claude"),
        str(Path.home() / ".local" / "bin" / "claude"),
    ],
    "codex": [
        "/Users/erik/.nvm/versions/node/v22.16.0/bin/codex",
        str(Path.home() / ".local" / "bin" / "codex"),
    ],
}


@dataclass
class ModelSpec:
    name: str
    runner: str  # "claude" | "codex"
    model: str = ""
    extra_args: list[str] = field(default_factory=list)


@dataclass
class TaskSpec:
    name: str
    title: str
    prompt: str
    timeout_s: int
    weights: dict[str, float]
    task_dir: Path

    @property
    def fixture_dir(self) -> Path:
        return self.task_dir / "fixture"

    @property
    def verify_script(self) -> Path:
        return self.task_dir / "verify.py"

    @property
    def solution_dir(self) -> Path:
        return self.task_dir / "solution"


@dataclass
class Config:
    trials: int
    concurrency: int
    default_timeout_s: int
    keep_workspace_days: int
    models: list[ModelSpec]
    claude_bin: str
    codex_bin: str
    codex_sandbox: str


def _resolve_bin(kind: str, configured: str) -> str:
    candidates = [configured] if configured else []
    found = shutil.which(kind)
    if found:
        candidates.append(found)
    candidates.extend(FALLBACK_BINS.get(kind, []))
    for c in candidates:
        if c and Path(c).exists():
            return c
    return kind  # last resort: rely on PATH at run time


def load_config(path: Path | None = None) -> Config:
    path = path or (REPO_ROOT / "config.toml")
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    run = raw.get("run", {})
    bins = raw.get("binaries", {})
    models = [
        ModelSpec(
            name=m["name"],
            runner=m["runner"],
            model=m.get("model", ""),
            extra_args=list(m.get("extra_args", [])),
        )
        for m in raw.get("models", [])
    ]
    if not models:
        raise SystemExit("config.toml defines no [[models]]")

    return Config(
        trials=int(run.get("trials", 2)),
        concurrency=int(run.get("concurrency", 4)),
        default_timeout_s=int(run.get("default_timeout_s", 420)),
        keep_workspace_days=int(run.get("keep_workspace_days", 7)),
        models=models,
        claude_bin=_resolve_bin("claude", bins.get("claude", "")),
        codex_bin=_resolve_bin("codex", bins.get("codex", "")),
        codex_sandbox=raw.get("codex", {}).get("sandbox", "workspace-write"),
    )


def load_tasks(names: list[str] | None = None) -> list[TaskSpec]:
    tasks = []
    for task_dir in sorted(TASKS_DIR.iterdir()):
        manifest = task_dir / "task.toml"
        if not manifest.exists():
            continue
        with open(manifest, "rb") as f:
            raw = tomllib.load(f)["task"]
        spec = TaskSpec(
            name=raw["name"],
            title=raw["title"],
            prompt=raw["prompt"].strip(),
            timeout_s=int(raw.get("timeout_s", 420)),
            weights={d: float(raw.get("weights", {}).get(d, 0.0)) for d in DIMENSIONS},
            task_dir=task_dir,
        )
        tasks.append(spec)
    if names:
        wanted = set(names)
        unknown = wanted - {t.name for t in tasks}
        if unknown:
            raise SystemExit(f"unknown tasks: {', '.join(sorted(unknown))}")
        tasks = [t for t in tasks if t.name in wanted]
    if not tasks:
        raise SystemExit("no tasks found under tasks/")
    return tasks
