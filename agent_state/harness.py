"""Orchestration: fan out (model, task, trial) jobs, verify, score, persist.

Multi-turn tasks: after turn 1 the workspace is snapshotted to
.solm/snapshots/turn1/, then each followup resumes the same agent session.
Verifiers may compare final state against the snapshot (cave-detection).

Infra errors (transport/auth/rate-limit) are retried once with a fresh
workspace; a repeat lands as status 'infra' and is excluded from scoring so a
529 never reads as model stupidity.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent_state import db, fingerprint, metrics
from agent_state.config import WORKSPACE_ROOT, Config, ModelSpec, TaskSpec
from agent_state.runners import RunResult, get_runner, merge_results

_print_lock = threading.Lock()


def _say(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def _prepare_workspace(task: TaskSpec, model: ModelSpec, trial: int, batch_id: str) -> Path:
    ws = WORKSPACE_ROOT / batch_id / model.name / f"{task.name}-t{trial}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(task.fixture_dir, ws)
    git = ["git", "-c", "user.email=agent-state@local", "-c", "user.name=agent-state", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q"], cwd=ws, capture_output=True)
    subprocess.run([*git, "add", "-A"], cwd=ws, capture_output=True)
    subprocess.run([*git, "commit", "-qm", "fixture"], cwd=ws, capture_output=True)
    return ws


def _snapshot(ws: Path, name: str) -> None:
    dest = ws / ".solm" / "snapshots" / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ws, dest,
        ignore=shutil.ignore_patterns(".git", ".solm", "__pycache__"),
    )


def run_verifier(task: TaskSpec, workspace: Path) -> tuple[float, dict, str]:
    """Execute the task's hidden verifier. Returns (score 0..1, checks, error)."""
    try:
        proc = subprocess.run(
            [sys.executable, str(task.verify_script), str(workspace)],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return 0.0, {}, "verifier timeout"
    out = proc.stdout.strip()
    try:
        payload = json.loads(out.splitlines()[-1]) if out else {}
        score = float(payload.get("score", 0.0))
        checks = payload.get("checks", {})
        return max(0.0, min(1.0, score)), checks, ""
    except (json.JSONDecodeError, ValueError, IndexError):
        return 0.0, {}, f"verifier output unparseable: {out[-300:]} {proc.stderr[-300:]}"


def _run_agent(cfg: Config, model: ModelSpec, task: TaskSpec, ws: Path) -> tuple[RunResult, list[str]]:
    """Run turn 1 plus any followups. Returns (merged result, followup messages)."""
    runner = get_runner(cfg, model)
    timeout = task.timeout_s or cfg.default_timeout_s
    first = runner.run(model, task.prompt, ws, timeout)
    results = [first]
    followup_messages: list[str] = []
    if task.followups and first.status == "ok":
        _snapshot(ws, "turn1")
        for i, followup in enumerate(task.followups, start=2):
            r = runner.resume(model, first.session_id, followup, ws, timeout,
                              log_prefix=f"turn{i}")
            results.append(r)
            followup_messages.append(r.final_message)
            if r.status != "ok":
                break
    return merge_results(results), followup_messages


def _run_one(cfg: Config, model: ModelSpec, task: TaskSpec, trial: int, batch_id: str, date: str) -> dict:
    label = f"{model.name} / {task.name} / t{trial}"
    _say(f"  ▶ {label}")

    ws = _prepare_workspace(task, model, trial, batch_id)
    result, followup_messages = _run_agent(cfg, model, task, ws)

    if result.status == "infra":
        _say(f"  ↻ {label}: infra error, retrying once ({result.error[:80]})")
        ws = _prepare_workspace(task, model, trial, batch_id)
        result, followup_messages = _run_agent(cfg, model, task, ws)

    score, checks, verr = 0.0, {}, ""
    if result.status not in ("timeout", "infra"):
        score, checks, verr = run_verifier(task, ws)

    changed = metrics.changed_files(task.fixture_dir, ws)
    flags, notes = metrics.laziness_scan(task.fixture_dir, ws, changed, result.final_message)
    over_flags, over_notes = metrics.overclaim_flags(result.final_message, score)
    flags += over_flags
    notes.extend(over_notes)
    if followup_messages:
        caves = metrics.cave_phrase_count(followup_messages)
        if caves:
            notes.append(f"cave-phrases x{caves} in followup replies")

    error = result.error or verr
    tag = f" [{result.status}]" if result.status != "ok" else ""
    _say(f"  ✔ {label}: score {score:.2f}"
         + (f", {flags} flags" if flags else "") + tag)
    return {
        "batch_id": batch_id,
        "date": date,
        "ts": dt.datetime.now().isoformat(timespec="seconds"),
        "model": model.name,
        "task": task.name,
        "trial": trial,
        "status": result.status,
        "score": score,
        "duration_s": round(result.duration_s, 1),
        "turns": result.turns,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": result.cost_usd,
        "laziness_flags": flags,
        "laziness_notes": "; ".join(notes)[:1000],
        "checks_json": json.dumps(checks),
        "workspace": str(ws),
        "error": error[:800],
    }


def prune_workspaces(keep_days: int) -> None:
    if not WORKSPACE_ROOT.exists():
        return
    cutoff = time.time() - keep_days * 86400
    for batch_dir in WORKSPACE_ROOT.iterdir():
        try:
            if batch_dir.is_dir() and batch_dir.stat().st_mtime < cutoff:
                shutil.rmtree(batch_dir, ignore_errors=True)
        except OSError:
            continue


def run_batch(
    cfg: Config,
    models: list[ModelSpec],
    tasks: list[TaskSpec],
    trials: int,
    trial_offset: int = 0,
) -> str:
    """Run the battery. Returns the batch date (YYYY-MM-DD)."""
    now = dt.datetime.now()
    date = now.strftime("%Y-%m-%d")
    batch_id = now.strftime("%Y%m%d-%H%M%S")
    prune_workspaces(cfg.keep_workspace_days)

    jobs = [
        (model, task, trial)
        for model in models
        for task in tasks
        for trial in range(trial_offset + 1, trial_offset + (model.trials or trials) + 1)
    ]
    per_model = ", ".join(f"{m.name} x{m.trials or trials}" for m in models)
    _say(f"state-of-llm batch {batch_id}: {len(jobs)} runs "
         f"({len(tasks)} tasks; trials: {per_model}), concurrency {cfg.concurrency}")

    conn = db.connect()
    fp = fingerprint.collect(cfg, tasks)
    db.insert_batch(conn, batch_id, date, now.isoformat(timespec="seconds"), json.dumps(fp))

    with ThreadPoolExecutor(max_workers=cfg.concurrency) as pool:
        futures = {
            pool.submit(_run_one, cfg, model, task, trial, batch_id, date): (model.name, task.name, trial)
            for model, task, trial in jobs
        }
        for fut in as_completed(futures):
            m, t, tr = futures[fut]
            try:
                row = fut.result()
            except Exception as e:  # a crashed job must not sink the batch
                row = {
                    "batch_id": batch_id, "date": date,
                    "ts": dt.datetime.now().isoformat(timespec="seconds"),
                    "model": m, "task": t, "trial": tr,
                    "status": "error", "score": 0.0, "duration_s": 0.0,
                    "turns": None, "input_tokens": None, "output_tokens": None,
                    "cost_usd": None, "laziness_flags": 0, "laziness_notes": "",
                    "checks_json": "{}", "workspace": "",
                    "error": f"harness exception: {e}"[:800],
                }
                _say(f"  ✖ {m} / {t} / t{tr}: harness exception: {e}")
            db.insert_run(conn, row)
    conn.close()
    return date
