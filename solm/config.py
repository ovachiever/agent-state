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

DIMENSIONS = ["intelligence", "tool_use", "diligence", "plot", "judgment"]

# One representative task per dimension for `solm run --quick`.
QUICK_TASKS = [
    "bugfix-intervals",
    "toolhunt-rename",
    "spec-checklist",
    "constraint-gauntlet",
    "infer-test-vs-code",
]

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
    enabled: bool = True  # disabled specs run only via `solm run --models <name>`
    trials: int | None = None  # per-model override of [run] trials (cost lever)


@dataclass
class TaskSpec:
    name: str
    title: str
    prompt: str
    timeout_s: int
    weights: dict[str, float]
    task_dir: Path
    followups: list[str] = field(default_factory=list)

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
class StatsConfig:
    material_drop: float = 6.0   # points of composite that matter to you
    baseline_window: int = 14    # trailing days used for task-paired baselines
    min_baseline_days: int = 3   # a task needs this many prior days to enter pairing
    bootstrap_iters: int = 2000
    cusum_k_sigma: float = 0.5   # slack per day, in sigma
    cusum_h_sigma: float = 4.0   # alarm threshold, in sigma


@dataclass
class Config:
    trials: int
    concurrency: int
    default_timeout_s: int
    keep_workspace_days: int
    models: list[ModelSpec]          # enabled specs — what a default run uses
    all_models: list[ModelSpec]      # every spec, for explicit --models selection
    claude_bin: str
    codex_bin: str
    codex_sandbox: str
    claude_strip_api_key: bool
    stats: StatsConfig


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
    stats_raw = raw.get("stats", {})
    all_models = [
        ModelSpec(
            name=m["name"],
            runner=m["runner"],
            model=m.get("model", ""),
            extra_args=list(m.get("extra_args", [])),
            enabled=bool(m.get("enabled", True)),
            trials=int(m["trials"]) if "trials" in m else None,
        )
        for m in raw.get("models", [])
    ]
    models = [m for m in all_models if m.enabled]
    if not models:
        raise SystemExit("config.toml defines no enabled [[models]]")

    return Config(
        trials=int(run.get("trials", 6)),
        concurrency=int(run.get("concurrency", 8)),
        default_timeout_s=int(run.get("default_timeout_s", 480)),
        keep_workspace_days=int(run.get("keep_workspace_days", 7)),
        models=models,
        all_models=all_models,
        claude_bin=_resolve_bin("claude", bins.get("claude", "")),
        codex_bin=_resolve_bin("codex", bins.get("codex", "")),
        codex_sandbox=raw.get("codex", {}).get("sandbox", "workspace-write"),
        claude_strip_api_key=bool(raw.get("claude", {}).get("strip_api_key", True)),
        stats=StatsConfig(
            material_drop=float(stats_raw.get("material_drop", 6.0)),
            baseline_window=int(stats_raw.get("baseline_window", 14)),
            min_baseline_days=int(stats_raw.get("min_baseline_days", 3)),
            bootstrap_iters=int(stats_raw.get("bootstrap_iters", 2000)),
            cusum_k_sigma=float(stats_raw.get("cusum_k_sigma", 0.5)),
            cusum_h_sigma=float(stats_raw.get("cusum_h_sigma", 4.0)),
        ),
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
            timeout_s=int(raw.get("timeout_s", 480)),
            weights={d: float(raw.get("weights", {}).get(d, 0.0)) for d in DIMENSIONS},
            task_dir=task_dir,
            followups=[f.strip() for f in raw.get("followups", [])],
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
