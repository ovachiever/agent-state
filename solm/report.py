"""Render the morning verdict: terminal (rich) and markdown."""

from __future__ import annotations

import datetime as dt

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from solm import db
from solm.config import DIMENSIONS, REPORTS_DIR, TaskSpec, load_tasks
from solm.scoring import DayScore, score_day

VERDICT_STYLE = {"GREEN": "bold green", "YELLOW": "bold yellow", "RED": "bold red"}
VERDICT_EMOJI = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}
VERDICT_CALL = {"GREEN": "CODE.", "YELLOW": "CODE, BUT VERIFY EVERYTHING.", "RED": "TOUCH GRASS."}
DIM_LABEL = {
    "intelligence": "Intelligence",
    "tool_use": "Tool use",
    "diligence": "Diligence",
    "plot": "Plot retention",
}
SPARK = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], lo: float = 40.0, hi: float = 100.0) -> str:
    if not values:
        return ""
    out = []
    for v in values:
        idx = int((max(lo, min(hi, v)) - lo) / (hi - lo) * (len(SPARK) - 1))
        out.append(SPARK[idx])
    return "".join(out)


def compute(date: str | None = None) -> tuple[str, dict[str, DayScore], list[dict], list[TaskSpec]]:
    conn = db.connect()
    date = date or db.latest_date(conn)
    if not date:
        raise SystemExit("no runs recorded yet — run `solm run` first")
    day_runs = db.fetch_runs(conn, date)
    all_runs = db.fetch_runs(conn)
    conn.close()
    tasks = load_tasks()
    return date, score_day(day_runs, all_runs, tasks), day_runs, tasks


def render(date: str | None = None, console: Console | None = None) -> None:
    console = console or Console()
    date, scores, day_runs, tasks = compute(date)

    console.print()
    console.print(f"[bold]STATE OF LLM[/bold] — {date}", justify="left")
    for model in sorted(scores):
        s = scores[model]
        style = VERDICT_STYLE[s.verdict]
        base = f"baseline {s.baseline}±{s.spread}" if s.baseline is not None else "no baseline yet"
        header = Text()
        header.append(f"{VERDICT_EMOJI[s.verdict]} {model}  ", style="bold")
        header.append(f"{s.verdict} {s.composite:.0f}", style=style)
        header.append(f"  ({base})  ", style="dim")
        header.append(VERDICT_CALL[s.verdict], style=style)
        body = Text()
        for dim in DIMENSIONS:
            body.append(f"  {DIM_LABEL[dim]:<15} {s.dims[dim]:5.1f}\n")
        trend = s.history + [s.composite]
        body.append(f"  {'Trend':<15} {sparkline(trend)}  ", style="dim")
        body.append(f"({s.reason})", style="dim")
        if s.avg_flags:
            body.append(f"\n  {'Laziness':<15} {s.avg_flags} flags/run avg", style="yellow")
        console.print(Panel(body, title=header, title_align="left", expand=False))

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
        ft = Table(title="Weak runs (score < 0.5 or errored)")
        for col in ("model", "task", "trial", "status", "score", "why / workspace"):
            ft.add_column(col)
        for r in failures:
            why = r["error"] or r["laziness_notes"] or ""
            ft.add_row(
                r["model"], r["task"], str(r["trial"]), r["status"],
                f"{r['score']:.2f}", (why[:60] + "\n" + r["workspace"]).strip(),
            )
        console.print(ft)
    console.print()


def save_markdown(date: str | None = None) -> str:
    date, scores, day_runs, tasks = compute(date)
    lines = [f"# State of LLM — {date}", ""]
    for model in sorted(scores):
        s = scores[model]
        base = f"baseline {s.baseline}±{s.spread}" if s.baseline is not None else "no baseline yet"
        lines.append(f"## {VERDICT_EMOJI[s.verdict]} {model}: {s.verdict} {s.composite:.0f} ({base}) — {VERDICT_CALL[s.verdict]}")
        lines.append("")
        for dim in DIMENSIONS:
            lines.append(f"- {DIM_LABEL[dim]}: {s.dims[dim]:.1f}")
        lines.append(f"- Laziness flags/run: {s.avg_flags}")
        lines.append(f"- Verdict basis: {s.reason}")
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
            lines.append(f"- {r['model']} / {r['task']} t{r['trial']}: {r['score']:.2f} ({r['status']}) — {why[:120]}")
            lines.append(f"  - workspace: `{r['workspace']}`")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{date}.md"
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def notify(date: str | None = None) -> None:
    """Post a macOS notification with the verdict line."""
    import subprocess

    try:
        date, scores, _, _ = compute(date)
    except SystemExit:
        return
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
    from solm.scoring import day_scores as _ds

    per_date: dict[str, dict[str, float]] = {}
    for date in dates:
        runs = [r for r in all_runs if r["date"] == date]
        scores = _ds(runs, tasks)
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
