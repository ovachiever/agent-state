"""solm: state-of-llm CLI."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from solm.config import load_config, load_tasks


def cmd_run(args) -> None:
    from solm import harness, report
    from solm.config import QUICK_TASKS

    cfg = load_config()
    models = cfg.models
    if args.models:
        wanted = set(args.models.split(","))
        unknown = wanted - {m.name for m in cfg.all_models}
        if unknown:
            raise SystemExit(f"unknown models: {', '.join(sorted(unknown))} "
                             f"(known: {', '.join(m.name for m in cfg.all_models)})")
        models = [m for m in cfg.all_models if m.name in wanted]
    task_names = args.tasks.split(",") if args.tasks else None
    if args.quick and not task_names:
        available = {t.name for t in load_tasks()}
        task_names = [t for t in QUICK_TASKS if t in available]
    tasks = load_tasks(task_names)
    trials = 1 if args.quick else (args.trials or cfg.trials)
    date = harness.run_batch(cfg, models, tasks, trials)

    if args.until_confident:
        _escalate_until_confident(cfg, models, tasks, date, trials, args.max_trials)
    report.render(date)


def _escalate_until_confident(cfg, models, tasks, date, base_trials, max_trials) -> None:
    from solm import harness, report

    trials_done = base_trials
    while trials_done < max_trials:
        _, scores, *_ = report.compute(date)
        needy = [m for m, s in scores.items() if s.needs_escalation]
        if not needy:
            break
        step = min(2, max_trials - trials_done)
        print(f"escalating: verdict underpowered for {', '.join(sorted(needy))} — +{step} trials")
        escalate_models = [m for m in models if m.name in needy]
        harness.run_batch(cfg, escalate_models, tasks, step, trial_offset=trials_done)
        trials_done += step


def cmd_daily(args) -> None:
    import datetime as dt
    import subprocess

    from solm import harness, report

    cfg = load_config()
    today = dt.date.today().isoformat()
    if cfg.auto_until and today > cfg.auto_until:
        # Dead-man's switch: notify first, then remove the plist, then stop.
        subprocess.run(
            ["osascript", "-e",
             'display notification "Auto-runs expired after the bake-in window. '
             'Renew: bump [schedule] auto_until + solm schedule install. '
             'Retire: nothing to do — the schedule removed itself." '
             'with title "State of LLM: kill-switch fired 🛑"'],
            capture_output=True,
        )
        from solm import schedule

        schedule.remove()
        print(f"kill-switch: auto_until {cfg.auto_until} passed; schedule uninstalled, no battery run")
        return

    tasks = load_tasks()
    date = harness.run_batch(cfg, cfg.models, tasks, cfg.trials)
    _escalate_until_confident(cfg, cfg.models, tasks, date, cfg.trials, max_trials=12)
    if cfg.anchor_daily:
        from solm import anchor

        for set_name in cfg.anchor_sets:
            try:
                anchor.run_set(cfg, set_name, tag="daily")
            except Exception as e:  # anchor trouble must never sink the battery report
                print(f"anchor {set_name} failed: {e}")
    path = report.save_markdown(date)
    if cfg.burnin.active(date):
        print(f"🔒 blind burn-in: verdicts sealed (report written to {path}, don't peek)")
    else:
        report.render(date)
        print(f"report saved: {path}")
    report.notify(date)


def _blind_gate(unseal: bool) -> bool:
    """True when output must stay sealed. Prints guidance when sealing."""
    import datetime as dt

    burnin = load_config().burnin
    today = dt.date.today().isoformat()
    if burnin.active(today) and not unseal:
        left = burnin.days_left(today)
        print(f"🔒 sealed: blinded burn-in, {left} day(s) left. "
              f"Log your gut first (solm gut fine|off). Use --unseal to break the blind on purpose.")
        return True
    return False


def cmd_report(args) -> None:
    from solm import report

    if _blind_gate(args.unseal):
        return
    report.render(args.date)
    if args.save:
        print(f"report saved: {report.save_markdown(args.date)}")


def cmd_verdict(args) -> None:
    from solm import report
    from solm.report import VERDICT_CALL, VERDICT_EMOJI

    if _blind_gate(args.unseal):
        return
    date, scores, *_ = report.compute(args.date)
    for model in sorted(scores):
        s = scores[model]
        print(f"{VERDICT_EMOJI[s.verdict]} {model}: {s.verdict} {s.composite:.0f} — {VERDICT_CALL[s.verdict]}")


def cmd_history(args) -> None:
    from solm import report

    report.history_table(args.days)


def cmd_gut(args) -> None:
    import datetime as dt

    from solm import db

    date = args.date or dt.date.today().isoformat()
    conn = db.connect()
    db.set_gut(conn, date, args.label, dt.datetime.now().isoformat(timespec="seconds"))
    conn.close()
    print(f"gut logged: {date} = {args.label}")


def cmd_burnin(args) -> None:
    import datetime as dt

    from solm import db
    from solm.scoring import score_day

    conn = db.connect()
    gut = db.fetch_gut(conn)
    all_runs = db.fetch_runs(conn)
    conn.close()

    burnin = load_config().burnin
    today = dt.date.today().isoformat()
    if burnin.active(today) and not args.unseal:
        run_dates = sorted({r["date"] for r in all_runs if r["date"] >= burnin.start})
        gut_dates = sorted(d for d in gut if d >= burnin.start)
        print(f"🔒 blinded burn-in in progress — {burnin.days_left(today)} day(s) left")
        print(f"   battery days recorded: {len(run_dates)}; gut labels logged: {len(gut_dates)}")
        missing = [d for d in run_dates if d not in gut]
        if missing:
            print(f"   days missing a gut label: {', '.join(missing)} "
                  f"(backfill: solm gut fine|off --date YYYY-MM-DD)")
        print("   comparison unlocks when the window ends (--unseal to break the blind).")
        return
    if not gut:
        raise SystemExit("no gut labels yet — log one with: solm gut fine|off")

    tasks = load_tasks()
    stats = load_config().stats
    agree = disagree = 0
    print(f"{'date':<12} {'gut':<6} {'verdict':<8} match")
    for date in sorted(gut):
        day = [r for r in all_runs if r["date"] == date]
        if not day:
            print(f"{date:<12} {gut[date]:<6} {'—':<8} (no runs that day)")
            continue
        scored = score_day(day, all_runs, tasks, stats)
        worst = max((s.verdict for s in scored.values()),
                    key=lambda v: ["GREEN", "YELLOW", "RED"].index(v))
        machine_off = worst != "GREEN"
        gut_off = gut[date] == "off"
        match = machine_off == gut_off
        agree += match
        disagree += not match
        print(f"{date:<12} {gut[date]:<6} {worst:<8} {'✔' if match else '✖'}")
    total = agree + disagree
    if total:
        print(f"\nagreement: {agree}/{total} ({100*agree/total:.0f}%) — "
              f"{'instrument tracking your gut' if agree/total >= 0.7 else 'not yet trustworthy'}")


def cmd_costs(args) -> None:
    from solm import db

    conn = db.connect()
    cur = conn.execute("""
        SELECT date, model, count(*) runs, round(sum(cost_usd), 2) usd,
               sum(input_tokens) in_tok, sum(output_tokens) out_tok
        FROM runs GROUP BY date, model ORDER BY date DESC, model LIMIT ?
    """, (args.days * 4,))
    rows = cur.fetchall()
    conn.close()
    pricing = load_config().pricing
    print(f"{'date':<12} {'model':<18} {'runs':>5} {'usd':>14} {'in-tok':>10} {'out-tok':>9}")
    total = 0.0
    for r in rows:
        in_tok, out_tok = r["in_tok"] or 0, r["out_tok"] or 0
        if r["usd"] is not None:
            total += r["usd"]
            usd = f"${r['usd']:.2f}"
        elif r["model"] in pricing:
            # Cache reads bill ~10% of input: show the honest range.
            p = pricing[r["model"]]
            lo = (in_tok * p["input"] * 0.1 + out_tok * p["output"]) / 1e6
            hi = (in_tok * p["input"] + out_tok * p["output"]) / 1e6
            total += lo
            usd = f"~${lo:.0f}-{hi:.0f}"
        else:
            usd = "tokens"
        print(f"{r['date']:<12} {r['model']:<18} {r['runs']:>5} {usd:>14} {in_tok:>10} {out_tok:>9}")
    print(f"\ntotal recorded/estimated-low API spend: ${total:.2f}")

    conn = db.connect()
    arows = conn.execute("""
        SELECT date, model, count(*) calls, sum(input_tokens) in_tok, sum(output_tokens) out_tok
        FROM anchor_runs GROUP BY date, model ORDER BY date DESC LIMIT ?
    """, (args.days * 4,)).fetchall()
    conn.close()
    if arows:
        print("\nanchor calls (raw API, tokens):")
        for r in arows:
            print(f"{r['date']:<12} {r['model']:<18} {r['calls']:>5} calls "
                  f"{r['in_tok'] or 0:>10} in {r['out_tok'] or 0:>9} out")


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


def cmd_anchor(args) -> None:
    from solm import anchor

    cfg = load_config()
    if args.action == "establish":
        anchor.run_set(cfg, args.set, tag="anchor", sample=args.sample, reps=args.reps)
        anchor.status(args.set)
    elif args.action == "run":
        anchor.run_set(cfg, args.set, tag="daily", sample=args.sample)
        anchor.status(args.set)
    else:
        anchor.status(args.set)


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
    p.add_argument("--quick", action="store_true", help="1 trial, one task per dimension")
    p.add_argument("--until-confident", action="store_true",
                   help="keep adding trials until the verdict is statistically resolved")
    p.add_argument("--max-trials", type=int, default=16,
                   help="escalation ceiling for --until-confident (default 16)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("daily", help="full battery + report + save + notify (what launchd runs)")
    p.set_defaults(func=cmd_daily)

    p = sub.add_parser("report", help="render report for a date (default: latest)")
    p.add_argument("--date")
    p.add_argument("--save", action="store_true")
    p.add_argument("--unseal", action="store_true", help="break the burn-in blind deliberately")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("verdict", help="one line per model: code or touch grass")
    p.add_argument("--date")
    p.add_argument("--unseal", action="store_true", help="break the burn-in blind deliberately")
    p.set_defaults(func=cmd_verdict)

    p = sub.add_parser("history", help="composite trend table")
    p.add_argument("--days", type=int, default=30)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("tasks", help="list the battery")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("gut", help="log your blinded felt-sense for the day (before looking!)")
    p.add_argument("label", choices=["fine", "off"])
    p.add_argument("--date", help="YYYY-MM-DD (default today)")
    p.set_defaults(func=cmd_gut)

    p = sub.add_parser("burnin", help="gut-vs-verdict agreement (progress view while blind)")
    p.add_argument("--unseal", action="store_true", help="break the burn-in blind deliberately")
    p.set_defaults(func=cmd_burnin)

    p = sub.add_parser("anchor", help="frozen-set absolute benchmarks via raw APIs")
    p.add_argument("action", choices=["establish", "run", "status"])
    p.add_argument("--set", default="aime30")
    p.add_argument("--reps", type=int, default=3, help="repetitions for establish")
    p.add_argument("--sample", type=int, help="only first N items (smoke test)")
    p.set_defaults(func=cmd_anchor)

    p = sub.add_parser("costs", help="recorded spend and tokens per day/model")
    p.add_argument("--days", type=int, default=14)
    p.set_defaults(func=cmd_costs)

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
