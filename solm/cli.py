"""solm: state-of-llm CLI."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from solm.config import load_config, load_tasks


def cmd_run(args) -> None:
    from solm import harness, report

    cfg = load_config()
    models = cfg.models
    if args.models:
        wanted = set(args.models.split(","))
        unknown = wanted - {m.name for m in models}
        if unknown:
            raise SystemExit(f"unknown models: {', '.join(sorted(unknown))} "
                             f"(known: {', '.join(m.name for m in models)})")
        models = [m for m in models if m.name in wanted]
    task_names = args.tasks.split(",") if args.tasks else None
    tasks = load_tasks(task_names)
    trials = 1 if args.quick else (args.trials or cfg.trials)
    if args.quick and not task_names:
        tasks = tasks[:3]
    date = harness.run_batch(cfg, models, tasks, trials)
    report.render(date)


def cmd_daily(args) -> None:
    from solm import harness, report

    cfg = load_config()
    date = harness.run_batch(cfg, cfg.models, load_tasks(), cfg.trials)
    report.render(date)
    path = report.save_markdown(date)
    print(f"report saved: {path}")
    report.notify(date)


def cmd_report(args) -> None:
    from solm import report

    report.render(args.date)
    if args.save:
        print(f"report saved: {report.save_markdown(args.date)}")


def cmd_verdict(args) -> None:
    from solm import report
    from solm.report import VERDICT_CALL, VERDICT_EMOJI

    date, scores, _, _ = report.compute(args.date)
    for model in sorted(scores):
        s = scores[model]
        print(f"{VERDICT_EMOJI[s.verdict]} {model}: {s.verdict} {s.composite:.0f} — {VERDICT_CALL[s.verdict]}")


def cmd_history(args) -> None:
    from solm import report

    report.history_table(args.days)


def cmd_tasks(args) -> None:
    for t in load_tasks():
        dims = ", ".join(f"{d}={w}" for d, w in t.weights.items() if w > 0)
        print(f"{t.name:<22} {t.title}  [{dims}]")


def cmd_selftest(args) -> None:
    from solm.selftest import run_selftest

    ok = run_selftest(args.tasks.split(",") if args.tasks else None)
    sys.exit(0 if ok else 1)


def cmd_doctor(args) -> None:
    cfg = load_config()
    ok = True
    for label, path in (("claude", cfg.claude_bin), ("codex", cfg.codex_bin)):
        exists = Path(path).exists() or shutil.which(path)
        print(f"{'✔' if exists else '✖'} {label}: {path}")
        ok = ok and bool(exists)
    print(f"✔ python: {sys.executable}")
    tasks = load_tasks()
    print(f"✔ tasks: {len(tasks)} ({', '.join(t.name for t in tasks)})")
    print(f"✔ models: {', '.join(m.name for m in cfg.models)}")
    from solm.db import DB_PATH

    print(f"{'✔' if DB_PATH.exists() else '·'} db: {DB_PATH}{'' if DB_PATH.exists() else ' (created on first run)'}")
    sys.exit(0 if ok else 1)


def cmd_schedule(args) -> None:
    from solm import schedule

    if args.action == "install":
        hh, mm = (args.at or "05:45").split(":")
        schedule.install(int(hh), int(mm))
    elif args.action == "remove":
        schedule.remove()
    else:
        schedule.status()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="solm",
        description="Daily vitals for the coding models you actually use.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="run the battery now")
    p.add_argument("--models", help="comma-separated model names (default: all)")
    p.add_argument("--tasks", help="comma-separated task names (default: all)")
    p.add_argument("--trials", type=int, help="trials per (model, task)")
    p.add_argument("--quick", action="store_true", help="1 trial, first 3 tasks")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("daily", help="full battery + report + save + notify (what launchd runs)")
    p.set_defaults(func=cmd_daily)

    p = sub.add_parser("report", help="render report for a date (default: latest)")
    p.add_argument("--date")
    p.add_argument("--save", action="store_true")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("verdict", help="one line per model: code or touch grass")
    p.add_argument("--date")
    p.set_defaults(func=cmd_verdict)

    p = sub.add_parser("history", help="composite trend table")
    p.add_argument("--days", type=int, default=30)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("tasks", help="list the battery")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("selftest", help="verify every task's verifier against its reference solution")
    p.add_argument("--tasks")
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser("doctor", help="check binaries, tasks, models, db")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("schedule", help="manage the launchd morning job")
    p.add_argument("action", choices=["install", "remove", "status"])
    p.add_argument("--at", help="HH:MM (default 05:45)")
    p.set_defaults(func=cmd_schedule)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
