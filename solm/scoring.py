"""Turn raw runs into dimension scores and a morning verdict.

Dimensions: intelligence, tool_use, diligence (anti-laziness), plot
(long-instruction retention). Each task contributes to dimensions per the
weights in its task.toml. Verdicts compare today against a trailing baseline
(median +/- MAD) so "the model got dumber" is measured, not vibes.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from solm.config import DIMENSIONS, TaskSpec

GREEN, YELLOW, RED = "GREEN", "YELLOW", "RED"

# Absolute floors used when there isn't enough history for a baseline,
# and as hard floors even when there is.
ABS_GREEN = 78.0
ABS_YELLOW = 60.0
BASELINE_MIN_DAYS = 3
BASELINE_WINDOW = 14
MIN_SPREAD = 4.0  # points; don't let a freakishly stable week make noise look like collapse
LAZINESS_PENALTY_PER_FLAG = 5.0  # off diligence, per average flag per run
LAZINESS_PENALTY_CAP = 30.0


@dataclass
class DayScore:
    model: str
    date: str
    dims: dict[str, float]                      # dimension -> 0..100
    composite: float
    task_scores: dict[str, float]               # task -> 0..1 (mean over trials)
    avg_flags: float
    run_count: int
    error_count: int
    verdict: str = ""
    reason: str = ""
    baseline: float | None = None
    spread: float | None = None
    history: list[float] = field(default_factory=list)  # prior composites, oldest first


def _weights_by_task(tasks: list[TaskSpec]) -> dict[str, dict[str, float]]:
    return {t.name: t.weights for t in tasks}


def day_scores(runs: list[dict], tasks: list[TaskSpec]) -> dict[str, DayScore]:
    """Aggregate one day's runs into per-model scores."""
    weights = _weights_by_task(tasks)
    by_model: dict[str, list[dict]] = {}
    for r in runs:
        by_model.setdefault(r["model"], []).append(r)

    out: dict[str, DayScore] = {}
    for model, mruns in by_model.items():
        by_task: dict[str, list[dict]] = {}
        for r in mruns:
            by_task.setdefault(r["task"], []).append(r)
        task_scores = {
            task: statistics.fmean(r["score"] for r in trs)
            for task, trs in by_task.items()
        }

        dims: dict[str, float] = {}
        for dim in DIMENSIONS:
            num = den = 0.0
            for task, score in task_scores.items():
                w = weights.get(task, {}).get(dim, 0.0)
                num += w * score
                den += w
            dims[dim] = round(100.0 * num / den, 1) if den > 0 else 0.0

        avg_flags = statistics.fmean(r["laziness_flags"] for r in mruns) if mruns else 0.0
        penalty = min(LAZINESS_PENALTY_CAP, LAZINESS_PENALTY_PER_FLAG * avg_flags)
        dims["diligence"] = round(max(0.0, dims["diligence"] - penalty), 1)

        composite = round(statistics.fmean(dims[d] for d in DIMENSIONS), 1)
        out[model] = DayScore(
            model=model,
            date=mruns[0]["date"],
            dims=dims,
            composite=composite,
            task_scores=task_scores,
            avg_flags=round(avg_flags, 2),
            run_count=len(mruns),
            error_count=sum(1 for r in mruns if r["status"] != "ok"),
        )
    return out


def history_composites(
    all_runs: list[dict], tasks: list[TaskSpec], model: str, before_date: str
) -> list[float]:
    """Composite per prior day for a model, oldest first, capped to the window."""
    by_date: dict[str, list[dict]] = {}
    for r in all_runs:
        if r["model"] == model and r["date"] < before_date:
            by_date.setdefault(r["date"], []).append(r)
    composites = []
    for date in sorted(by_date):
        scores = day_scores(by_date[date], tasks)
        if model in scores:
            composites.append(scores[model].composite)
    return composites[-BASELINE_WINDOW:]


def apply_verdict(score: DayScore, history: list[float]) -> None:
    """Attach verdict + reason to a DayScore, mutating it."""
    score.history = history
    if len(history) >= BASELINE_MIN_DAYS:
        baseline = statistics.median(history)
        mad = statistics.median(abs(h - baseline) for h in history)
        spread = max(mad * 1.4826, MIN_SPREAD)
        score.baseline, score.spread = round(baseline, 1), round(spread, 1)
        delta = score.composite - baseline
        if score.composite < ABS_YELLOW or delta < -2 * spread:
            score.verdict = RED
            score.reason = f"composite {score.composite} vs baseline {baseline:.0f} (Δ{delta:+.1f}, band ±{spread:.1f})"
        elif delta < -spread:
            score.verdict = YELLOW
            score.reason = f"below baseline {baseline:.0f} by {-delta:.1f} (band ±{spread:.1f})"
        elif score.composite < ABS_GREEN:
            score.verdict = YELLOW
            score.reason = f"at baseline but composite {score.composite} under {ABS_GREEN:.0f}"
        else:
            score.verdict = GREEN
            score.reason = f"at or above baseline {baseline:.0f} (Δ{delta:+.1f})"
    else:
        if score.composite >= ABS_GREEN:
            score.verdict = GREEN
        elif score.composite >= ABS_YELLOW:
            score.verdict = YELLOW
        else:
            score.verdict = RED
        score.reason = f"absolute bands (only {len(history)} days of history)"

    if score.error_count > score.run_count // 2 and score.verdict == GREEN:
        score.verdict = YELLOW
        score.reason += f"; {score.error_count}/{score.run_count} runs errored"


def score_day(
    day_runs: list[dict], all_runs: list[dict], tasks: list[TaskSpec]
) -> dict[str, DayScore]:
    scores = day_scores(day_runs, tasks)
    for model, score in scores.items():
        history = history_composites(all_runs, tasks, model, score.date)
        apply_verdict(score, history)
    return scores
