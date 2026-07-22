"""Turn raw runs into dimension scores, statistical effects, and a verdict.

The measurement model, in order of leverage:

1. PAIRING. Today's per-task means are compared against the same task's own
   trailing-window baseline. Between-task difficulty variance (the biggest
   noise source) cancels out entirely; what remains is measurement noise.
2. BOOTSTRAP. Today's trials and the baseline runs are resampled per task to
   put a 95% CI on the day effect, and the CI drives the verdict. The report
   also prints the minimum detectable effect (MDE ≈ 2.8·SE) so a quiet day
   states what it could and could not have seen.
3. CUSUM. A slow decay hides inside any trailing baseline (the frog boils).
   The cumulative-sum detector accumulates small daily deficits and alarms
   when their sum crosses h·sigma, catching drift no single day would flag.

Infra-status runs are excluded everywhere: a rate-limit is not a model property.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field

from agent_state.config import DIMENSIONS, StatsConfig, TaskSpec

GREEN, YELLOW, RED = "GREEN", "YELLOW", "RED"

ABS_GREEN = 78.0
ABS_YELLOW = 60.0
ABS_FLOOR_RED = 55.0
LAZINESS_PENALTY_PER_FLAG = 5.0
LAZINESS_PENALTY_CAP = 30.0
CUSUM_MIN_DAYS = 8
CUSUM_MIN_ANCHOR = 5   # prior days needed before a deviation is trustworthy
SIGMA_FLOOR = 2.0  # points; guards divide-by-zero on eerily stable histories


@dataclass
class DayScore:
    model: str
    date: str
    dims: dict[str, float | None]  # None = dimension not exercised in this run
    composite: float
    task_scores: dict[str, float]
    avg_flags: float
    run_count: int
    error_count: int
    infra_count: int
    verdict: str = ""
    reason: str = ""
    needs_escalation: bool = False
    day_effect: float | None = None      # points vs task-paired baseline
    ci_low: float | None = None
    ci_high: float | None = None
    mde: float | None = None             # min detectable effect at current N
    paired_tasks: int = 0
    cusum_sigma: float | None = None     # current CUSUM statistic, in sigmas
    cusum_alarm: bool = False
    baseline: float | None = None        # legacy trailing-median band (display)
    spread: float | None = None
    history: list[float] = field(default_factory=list)


def scored(runs: list[dict]) -> list[dict]:
    return [r for r in runs if r["status"] != "infra"]


def task_composite_weights(tasks: list[TaskSpec], present: set[str]) -> dict[str, float]:
    """Each task's contribution to the composite, matching day_scores math."""
    active_dims = []
    totals = {}
    for d in DIMENSIONS:
        total = sum(t.weights[d] for t in tasks if t.name in present)
        if total > 0:
            active_dims.append(d)
            totals[d] = total
    if not active_dims:
        return {}
    c = {}
    for t in tasks:
        if t.name not in present:
            continue
        c[t.name] = sum(t.weights[d] / totals[d] for d in active_dims) / len(active_dims)
    return c


def day_scores(runs: list[dict], tasks: list[TaskSpec]) -> dict[str, DayScore]:
    """Aggregate one day's runs into per-model scores (infra excluded)."""
    weights = {t.name: t.weights for t in tasks}
    by_model: dict[str, list[dict]] = {}
    for r in runs:
        by_model.setdefault(r["model"], []).append(r)

    out: dict[str, DayScore] = {}
    for model, mruns in by_model.items():
        usable = scored(mruns)
        infra_count = len(mruns) - len(usable)
        by_task: dict[str, list[dict]] = {}
        for r in usable:
            by_task.setdefault(r["task"], []).append(r)
        task_scores = {
            task: statistics.fmean(r["score"] for r in trs)
            for task, trs in by_task.items()
        }

        dims: dict[str, float | None] = {}
        for dim in DIMENSIONS:
            num = den = 0.0
            for task, score in task_scores.items():
                w = weights.get(task, {}).get(dim, 0.0)
                num += w * score
                den += w
            dims[dim] = round(100.0 * num / den, 1) if den > 0 else None

        avg_flags = statistics.fmean(r["laziness_flags"] for r in usable) if usable else 0.0
        penalty = min(LAZINESS_PENALTY_CAP, LAZINESS_PENALTY_PER_FLAG * avg_flags)
        if dims["diligence"] is not None:
            dims["diligence"] = round(max(0.0, dims["diligence"] - penalty), 1)

        active = [v for d in DIMENSIONS if (v := dims[d]) is not None]
        composite = round(statistics.fmean(active), 1) if active else 0.0
        out[model] = DayScore(
            model=model,
            date=mruns[0]["date"],
            dims=dims,
            composite=composite,
            task_scores=task_scores,
            avg_flags=round(avg_flags, 2),
            run_count=len(mruns),
            error_count=sum(1 for r in usable if r["status"] != "ok"),
            infra_count=infra_count,
        )
    return out


def _task_baselines(
    all_runs: list[dict], model: str, before_date: str, stats: StatsConfig
) -> dict[str, list[float]]:
    """Per-task baseline scores from the trailing window (infra excluded).

    A task qualifies only with >= min_baseline_days distinct prior days.
    """
    by_task_day: dict[str, dict[str, list[float]]] = {}
    dates = sorted({r["date"] for r in all_runs if r["model"] == model and r["date"] < before_date})
    window = set(dates[-stats.baseline_window:])
    for r in all_runs:
        if r["model"] != model or r["date"] not in window or r["status"] == "infra":
            continue
        by_task_day.setdefault(r["task"], {}).setdefault(r["date"], []).append(r["score"])
    out = {}
    for task, days in by_task_day.items():
        if len(days) >= stats.min_baseline_days:
            out[task] = [s for scores in days.values() for s in scores]
    return out


def paired_day_effect(
    day_runs: list[dict],
    all_runs: list[dict],
    tasks: list[TaskSpec],
    model: str,
    date: str,
    stats: StatsConfig,
    with_bootstrap: bool = True,
) -> tuple[float | None, float | None, float | None, float | None, int]:
    """(effect_points, ci_low, ci_high, mde, paired_task_count).

    effect = weighted mean over paired tasks of (today_mean - baseline_mean),
    scaled to composite points. None when no task has a usable baseline.
    """
    baselines = _task_baselines(all_runs, model, date, stats)
    today: dict[str, list[float]] = {}
    for r in day_runs:
        if r["model"] == model and r["status"] != "infra":
            today.setdefault(r["task"], []).append(r["score"])

    paired = sorted(set(baselines) & set(today))
    if not paired:
        return None, None, None, None, 0

    weights = task_composite_weights(tasks, set(paired))
    total_w = sum(weights.get(t, 0.0) for t in paired)
    if total_w <= 0:
        return None, None, None, None, 0

    def effect_of(today_s: dict[str, list[float]], base_s: dict[str, list[float]]) -> float:
        acc = 0.0
        for t in paired:
            delta = statistics.fmean(today_s[t]) - statistics.fmean(base_s[t])
            acc += (weights.get(t, 0.0) / total_w) * delta
        return acc * 100.0

    point = effect_of(today, baselines)
    if not with_bootstrap:
        return round(point, 2), None, None, None, len(paired)

    # Two-level bootstrap: resample tasks (clusters), then trials within each.
    # Task-level resampling is what keeps the CI honest at 1 trial/task, where
    # within-task resampling alone would degenerate to zero variance.
    rng = random.Random(f"{model}:{date}")  # deterministic per (model, date)
    boots = []
    for _ in range(stats.bootstrap_iters):
        sampled = [rng.choice(paired) for _ in paired]
        acc = 0.0
        w_total = sum(weights.get(t, 0.0) for t in sampled)
        if w_total <= 0:
            continue
        for t in sampled:
            t_scores = [rng.choice(today[t]) for _ in today[t]]
            b_scores = [rng.choice(baselines[t]) for _ in baselines[t]]
            delta = statistics.fmean(t_scores) - statistics.fmean(b_scores)
            acc += (weights.get(t, 0.0) / w_total) * delta
        boots.append(acc * 100.0)
    boots.sort()
    n = len(boots)
    ci_low = boots[int(0.025 * n)]
    ci_high = boots[int(0.975 * n) - 1]
    se = statistics.pstdev(boots) if n > 1 else 0.0
    mde = 2.8 * se  # alpha=.05 two-sided, 80% power
    return round(point, 2), round(ci_low, 2), round(ci_high, 2), round(mde, 2), len(paired)


def anchored_deviations(history: list[float]) -> list[float]:
    """Per-day composite deviations from the median of strictly PRIOR days.

    Anchoring on prior data only keeps successive deviations (near-)independent;
    a rolling shared baseline would correlate them and let pure noise
    accumulate into a fake drift (observed: ~15% false alarms in simulation).
    """
    devs = []
    for i in range(CUSUM_MIN_ANCHOR, len(history)):
        anchor = statistics.median(history[:i])
        devs.append(history[i] - anchor)
    return devs


def cusum(
    series: list[float], today_dev: float | None, stats: StatsConfig
) -> tuple[float | None, bool]:
    """One-sided CUSUM on daily deficits. Returns (statistic in sigmas, alarm)."""
    points = list(series)
    if today_dev is not None:
        points.append(today_dev)
    if len(points) < CUSUM_MIN_DAYS:
        return None, False
    med = statistics.median(points)
    mad = statistics.median(abs(p - med) for p in points)
    sigma = max(mad * 1.4826, SIGMA_FLOOR)
    k = stats.cusum_k_sigma * sigma
    h = stats.cusum_h_sigma * sigma
    s = 0.0
    for e in points:
        s = max(0.0, s + (-e - k))
    alarm = s >= h
    # A drift alarm on a day that itself looks fine is stale news, not a verdict.
    if today_dev is not None and today_dev > -stats.cusum_gate:
        alarm = False
    return round(s / sigma, 2), alarm


def history_composites(
    all_runs: list[dict], tasks: list[TaskSpec], model: str, before_date: str, window: int
) -> list[float]:
    by_date: dict[str, list[dict]] = {}
    for r in all_runs:
        if r["model"] == model and r["date"] < before_date:
            by_date.setdefault(r["date"], []).append(r)
    composites = []
    for date in sorted(by_date):
        scores = day_scores(by_date[date], tasks)
        if model in scores:
            composites.append(scores[model].composite)
    return composites[-window:]


def apply_verdict(score: DayScore, stats: StatsConfig) -> None:
    material = stats.material_drop
    e, lo, hi = score.day_effect, score.ci_low, score.ci_high

    if score.composite < ABS_FLOOR_RED:
        score.verdict, score.reason = RED, f"composite {score.composite} below hard floor {ABS_FLOOR_RED:.0f}"
    elif e is None:
        if score.composite >= ABS_GREEN:
            score.verdict = GREEN
        elif score.composite >= ABS_YELLOW:
            score.verdict = YELLOW
        else:
            score.verdict = RED
        score.reason = "absolute bands — task baselines still building"
    elif hi is not None and hi < 0 and e < -material:
        score.verdict = RED
        score.reason = f"confident regression: {e:+.1f} pts (95% CI {lo:+.1f}..{hi:+.1f})"
    elif score.cusum_alarm and e <= 0:
        score.verdict = RED
        score.reason = f"sustained drift alarm (CUSUM {score.cusum_sigma}σ) — slow decay, not a one-day blip"
    elif hi is not None and hi < 0:
        score.verdict = YELLOW
        score.reason = f"significant but sub-material drop: {e:+.1f} pts (CI {lo:+.1f}..{hi:+.1f})"
    elif e < -material:
        score.verdict = YELLOW
        score.needs_escalation = True
        score.reason = f"drop of {e:+.1f} pts but CI straddles zero — underpowered, escalate trials"
    elif score.composite < ABS_GREEN:
        score.verdict = YELLOW
        score.reason = f"near baseline ({e:+.1f} pts) but composite {score.composite} under {ABS_GREEN:.0f}"
    else:
        score.verdict = GREEN
        score.reason = f"within noise of baseline ({e:+.1f} pts, CI {lo:+.1f}..{hi:+.1f})"

    # Deliberately NO escalation on "GREEN but underpowered": buying precision
    # to confirm good news is wasted spend. Escalation exists for suspicion only
    # (the ambiguous-drop branch above).
    if score.mde is not None and score.mde > material and score.verdict == GREEN:
        score.reason += f" (MDE {score.mde:.1f} at today's N)"

    usable = score.run_count - score.infra_count
    if score.infra_count > usable and score.verdict != RED:
        score.verdict = YELLOW
        score.reason += f"; {score.infra_count}/{score.run_count} runs were infra failures — read with suspicion"


def score_day(
    day_runs: list[dict], all_runs: list[dict], tasks: list[TaskSpec], stats: StatsConfig
) -> dict[str, DayScore]:
    scores = day_scores(day_runs, tasks)
    for model, score in scores.items():
        effect, lo, hi, mde, paired = paired_day_effect(
            day_runs, all_runs, tasks, model, score.date, stats
        )
        score.day_effect, score.ci_low, score.ci_high = effect, lo, hi
        score.mde, score.paired_tasks = mde, paired

        drift_history = history_composites(all_runs, tasks, model, score.date, 60)
        today_dev = (
            score.composite - statistics.median(drift_history)
            if len(drift_history) >= CUSUM_MIN_ANCHOR else None
        )
        score.cusum_sigma, score.cusum_alarm = cusum(
            anchored_deviations(drift_history), today_dev, stats
        )

        history = history_composites(all_runs, tasks, model, score.date, stats.baseline_window)
        score.history = history
        if len(history) >= stats.min_baseline_days:
            baseline = statistics.median(history)
            mad = statistics.median(abs(h - baseline) for h in history)
            score.baseline = round(baseline, 1)
            score.spread = round(max(mad * 1.4826, 4.0), 1)

        apply_verdict(score, stats)
    return scores
