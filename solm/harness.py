"""Orchestration: fan out (model, task, trial) jobs, verify, score, persist."""

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

from solm import db, metrics
from solm.config import WORKSPACE_ROOT, Config, ModelSpec, TaskSpec
from solm.runners import get_runner

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
    git = ["git", "-c", "user.email=solm@local", "-c", "user.name=solm", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q"], cwd=ws, capture_output=True)
    subprocess.run([*git, "add", "-A"], cwd=ws, capture_output=True)
    subprocess.run([*git, "commit", "-qm", "fixture"], cwd=ws, capture_output=True)
    return ws


def run_verifier(task: TaskSpec, workspace: Path) -> tuple[float, dict, str]:
    """Execute the task's hidden verifier against a workspace.

    Returns (score 0..1, checks dict, error string).
    """
    try:
        proc = subprocess.run(
            [sys.executable, str(task.verify_script), str(workspace)],
            capture_output=True,
            text=True,
            timeout=120,
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


def _run_one(cfg: Config, model: ModelSpec, task: TaskSpec, trial: int, batch_id: str, date: str) -> dict:
    ws = _prepare_workspace(task, model, trial, batch_id)
    runner = get_runner(cfg, model)
    label = f"{model.name} / {task.name} / t{trial}"
    _say(f"  ▶ {label}")
    result = runner.run(model, task.prompt, ws, task.timeout_s or cfg.default_timeout_s)

    score, checks, verr = 0.0, {}, ""
    if result.status != "timeout":
        score, checks, verr = run_verifier(task, ws)
    changed = metrics.changed_files(task.fixture_dir, ws)
    flags, notes = metrics.laziness_scan(task.fixture_dir, ws, changed, result.final_message)

    error = result.error or verr
    _say(
        f"  ✔ {label}: score {score:.2f}"
        + (f", {flags} laziness flags" if flags else "")
        + (f" [{result.status}]" if result.status != "ok" else "")
    )
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
        for trial in range(1, trials + 1)
    ]
    _say(f"state-of-llm batch {batch_id}: {len(jobs)} runs "
         f"({len(models)} models x {len(tasks)} tasks x {trials} trials), "
         f"concurrency {cfg.concurrency}")

    conn = db.connect()
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
