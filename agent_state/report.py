"""Render the morning verdict: terminal (rich) and markdown."""

from __future__ import annotations

import json
import statistics

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent_state import db, fingerprint
from agent_state.config import DIMENSIONS, REPORTS_DIR, TaskSpec, load_config, load_tasks
from agent_state.scoring import DayScore, day_scores, score_day

VERDICT_STYLE = {"GREEN": "bold green", "YELLOW": "bold yellow", "RED": "bold red"}
VERDICT_EMOJI = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}
VERDICT_CALL = {"GREEN": "CODE.", "YELLOW": "CODE, BUT VERIFY EVERYTHING.", "RED": "TOUCH GRASS."}
DIM_LABEL = {
    "intelligence": "Intelligence",
    "tool_use": "Tool use",
    "diligence": "Diligence",
    "plot": "Plot retention",
    "judgment": "Judgment",
}
SPARK = "▁▂▃▄▅▆▇█"
CEILING_MEAN = 0.95


def sparkline(values: list[float], lo: float = 40.0, hi: float = 100.0) -> str:
    if not values:
        return ""
    out = []
    for v in values:
        idx = int((max(lo, min(hi, v)) - lo) / (hi - lo) * (len(SPARK) - 1))
        out.append(SPARK[idx])
    return "".join(out)


def compute(date: str | None = None):
    conn = db.connect()
    date = date or db.latest_date(conn)
    if not date:
        raise SystemExit("no runs recorded yet — run `agent-state run` first")
    day_runs = db.fetch_runs(conn, date)
    all_runs = db.fetch_runs(conn)
    batches = db.fetch_batches(conn)
    conn.close()
    tasks = load_tasks()
    stats = load_config().stats
    return date, score_day(day_runs, all_runs, tasks, stats), day_runs, all_runs, tasks, batches


def _fingerprint_warnings(batches: list[dict], date: str) -> list[str]:
    """What changed about the yardstick between the previous batch and today's."""
    fps = [(b["date"], json.loads(b["fingerprint_json"] or "{}")) for b in batches]
    fps = [f for f in fps if f[1]]
    todays = [f for f in fps if f[0] == date]
    priors = [f for f in fps if f[0] < date]
    if not todays or not priors:
        return []
    changes = fingerprint.diff(priors[-1][1], todays[-1][1])
    if not changes:
        return []
    return [f"yardstick changed since {priors[-1][0]}: {', '.join(changes)}"]


def _ceiling_warnings(all_runs: list[dict], tasks: list[TaskSpec], date: str) -> list[str]:
    """Tasks everyone aces carry no information about degradation."""
    warnings = []
    for task in tasks:
        scores = [r["score"] for r in all_runs
                  if r["task"] == task.name and r["status"] != "infra" and r["date"] <= date]
        if len(scores) >= 8 and statistics.fmean(scores) >= CEILING_MEAN:
            warnings.append(
                f"ceiling: {task.name} mean {statistics.fmean(scores):.2f} over {len(scores)} runs — "
                "little signal, consider hardening"
            )
    return warnings


def render(date: str | None = None, console: Console | None = None) -> None:
    console = console or Console()
    date, scores, day_runs, all_runs, tasks, batches = compute(date)

    console.print()
    console.print(f"[bold]STATE OF LLM[/bold] — {date}")
    for model in sorted(scores):
        s = scores[model]
        style = VERDICT_STYLE[s.verdict]
        header = Text()
        header.append(f"{VERDICT_EMOJI[s.verdict]} {model}  ", style="bold")
        header.append(f"{s.verdict} {s.composite:.0f}", style=style)
        header.append(f"  {VERDICT_CALL[s.verdict]}", style=style)

        body = Text()
        for dim in DIMENSIONS:
            v = s.dims[dim]
            body.append(f"  {DIM_LABEL[dim]:<15} {v:5.1f}\n" if v is not None
                        else f"  {DIM_LABEL[dim]:<15}     —\n")
        if s.day_effect is not None:
            body.append(
                f"  {'Day effect':<15} {s.day_effect:+.1f} pts "
                f"(95% CI {s.ci_low:+.1f}..{s.ci_high:+.1f}, {s.paired_tasks} tasks paired)\n"
            )
            body.append(f"  {'Sensitivity':<15} MDE ≈ {s.mde:.1f} pts at today's N\n")
        else:
            body.append(f"  {'Day effect':<15} n/a — baselines building\n", style="dim")
        if s.cusum_sigma is not None:
            drift = f"CUSUM {s.cusum_sigma:.1f}σ"
            body.append(f"  {'Drift':<15} {drift}"
                        + ("  ⚠ ALARM\n" if s.cusum_alarm else " (alarm at 4σ)\n"),
                        style="bold red" if s.cusum_alarm else None)
        if s.infra_count:
            body.append(f"  {'Infra':<15} {s.infra_count} runs excluded (transport/auth)\n", style="yellow")
        if s.avg_flags:
            body.append(f"  {'Behavior flags':<15} {s.avg_flags}/run avg\n", style="yellow")
        trend = s.history + [s.composite]
        body.append(f"  {'Trend':<15} {sparkline(trend)}\n", style="dim")
        body.append(f"  {s.reason}", style="dim")
        console.print(Panel(body, title=header, title_align="left", expand=False))

    warnings = _fingerprint_warnings(batches, date) + _ceiling_warnings(all_runs, tasks, date)
    for w in warnings:
        console.print(f"  [yellow]⚠ {w}[/yellow]")

    table = Table(title=f"Per-task scores (mean of trials) — {date}", show_lines=False)
    table.add_column("Task")
    models = sorted(scores)
    for m in models:
        table.add_column(m, justify="right")
    for task in tasks:
        row = [task.name]
        for m in models:
            v = scores[m].task_scores.get(task.name)
            row.append(f"{v:.2f}" if v is not None else "—")
        table.add_row(*row)
    console.print(table)

    failures = [r for r in day_runs if r["status"] != "ok" or r["score"] < 0.5]
    if failures:
        ft = Table(title="Weak runs (score < 0.5 or non-ok)")
        for col in ("model", "task", "trial", "status", "score", "why / workspace"):
            ft.add_column(col)
        for r in failures:
            why = r["error"] or r["laziness_notes"] or ""
            ft.add_row(
                r["model"], r["task"], str(r["trial"]), r["status"],
                f"{r['score']:.2f}", (why[:70] + "\n" + r["workspace"]).strip(),
            )
        console.print(ft)
    console.print()


def save_markdown(date: str | None = None) -> str:
    date, scores, day_runs, all_runs, tasks, batches = compute(date)
    lines = [f"# State of LLM — {date}", ""]
    for model in sorted(scores):
        s = scores[model]
        lines.append(f"## {VERDICT_EMOJI[s.verdict]} {model}: {s.verdict} {s.composite:.0f} — {VERDICT_CALL[s.verdict]}")
        lines.append("")
        for dim in DIMENSIONS:
            v = s.dims[dim]
            lines.append(f"- {DIM_LABEL[dim]}: {v:.1f}" if v is not None else f"- {DIM_LABEL[dim]}: —")
        if s.day_effect is not None:
            lines.append(f"- Day effect: {s.day_effect:+.1f} pts (95% CI {s.ci_low:+.1f}..{s.ci_high:+.1f}), MDE {s.mde:.1f}")
        if s.cusum_sigma is not None:
            lines.append(f"- Drift: CUSUM {s.cusum_sigma:.1f}σ{' ⚠ ALARM' if s.cusum_alarm else ''}")
        lines.append(f"- Behavior flags/run: {s.avg_flags}; infra excluded: {s.infra_count}")
        lines.append(f"- Verdict basis: {s.reason}")
        lines.append("")
    for w in _fingerprint_warnings(batches, date) + _ceiling_warnings(all_runs, tasks, date):
        lines.append(f"> ⚠ {w}")
    lines.append("")
    lines.append("## Per-task")
    lines.append("")
    models = sorted(scores)
    lines.append("| task | " + " | ".join(models) + " |")
    lines.append("|---" * (len(models) + 1) + "|")
    for task in tasks:
        cells = [
            f"{scores[m].task_scores[task.name]:.2f}" if task.name in scores[m].task_scores else "—"
            for m in models
        ]
        lines.append(f"| {task.name} | " + " | ".join(cells) + " |")
    lines.append("")
    failures = [r for r in day_runs if r["status"] != "ok" or r["score"] < 0.5]
    if failures:
        lines.append("## Weak runs")
        lines.append("")
        for r in failures:
            why = r["error"] or r["laziness_notes"] or "low score"
            lines.append(f"- {r['model']} / {r['task']} t{r['trial']}: {r['score']:.2f} ({r['status']}) — {why[:140]}")
            lines.append(f"  - workspace: `{r['workspace']}`")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{date}.md"
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def notify(date: str | None = None) -> None:
    """Post a macOS notification. During the blinded burn-in it carries NO
    verdict — the light must not peek at the observer."""
    import subprocess

    try:
        date, scores, day_runs, *_ = compute(date)
    except SystemExit:
        return
    if load_config().burnin.active(date):
        title = "State of LLM: battery complete 🔒"
        msg = f"{len(day_runs)} runs recorded. Log your gut: agent-state gut fine|off"
    else:
        parts = [f"{VERDICT_EMOJI[s.verdict]} {m} {s.composite:.0f}" for m, s in sorted(scores.items())]
        worst = max((s.verdict for s in scores.values()),
                    key=lambda v: ["GREEN", "YELLOW", "RED"].index(v))
        msg = "  ".join(parts)
        title = f"State of LLM: {VERDICT_CALL[worst]}"
    subprocess.run(
        ["osascript", "-e",
         f'display notification "{msg}" with title "{title}"'],
        capture_output=True,
    )


def history_table(days: int = 30, console: Console | None = None) -> None:
    console = console or Console()
    conn = db.connect()
    all_runs = db.fetch_runs(conn)
    dates = db.fetch_dates(conn)[-days:]
    conn.close()
    if not dates:
        raise SystemExit("no history yet")
    tasks = load_tasks()

    models = sorted({r["model"] for r in all_runs})
    table = Table(title=f"Composite history (last {len(dates)} days)")
    table.add_column("date")
    for m in models:
        table.add_column(m, justify="right")

    per_date: dict[str, dict[str, float]] = {}
    for date in dates:
        runs = [r for r in all_runs if r["date"] == date]
        scores = day_scores(runs, tasks)
        per_date[date] = {m: s.composite for m, s in scores.items()}
    for date in dates:
        row = [date] + [
            f"{per_date[date][m]:.0f}" if m in per_date[date] else "—" for m in models
        ]
        table.add_row(*row)
    trend_row = ["trend"] + [
        sparkline([per_date[d][m] for d in dates if m in per_date[d]]) for m in models
    ]
    table.add_row(*trend_row)
    console.print(table)
