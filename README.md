# state-of-llm

Daily vitals for the coding models you actually use. Wake up, read one line per
model: 🟢 **CODE.** or 🔴 **TOUCH GRASS.**

Every morning it runs a fixed six-task battery through the **real CLIs you code
with** — `claude` (Fable, your settings.json effort) and `codex exec` (your
`~/.codex/config.toml` model and effort) — in isolated throwaway workspaces.
Hidden verifiers score each run mechanically, results accumulate in SQLite, and
today gets judged against your trailing 14-day baseline (median ± MAD). A fixed
battery is the point: an unchanging yardstick makes model/harness drift visible.

## The verdict

- 🟢 **GREEN** — at or above baseline. Code.
- 🟡 **YELLOW** — one band below baseline, or composite under 78. Code, but verify everything.
- 🔴 **RED** — two bands below baseline or composite under 60. Touch grass.

Until 3 days of history exist, absolute bands apply (≥78 green, ≥60 yellow).

## Dimensions

| Dimension | What it measures | Fed by |
|---|---|---|
| Intelligence | correctness against a spec, edge cases included | bugfix-intervals, feature-ttl-cache |
| Tool use | search, multi-file edits, repo-convention adherence | toolhunt-rename, wiring-plugin |
| Diligence | anti-laziness: no stubs, TODOs, partial work, deferrals | spec-checklist + cross-task laziness scan |
| Plot retention | holding 12 scattered constraints across a long brief | constraint-gauntlet, wiring-plugin |

Laziness is also scanned on every run (new TODO/FIXME/NotImplementedError/
placeholder text in touched files, deferral phrases in the final message,
zero-diff giveups) and penalizes Diligence directly.

## Commands

```bash
.venv/bin/solm verdict              # the morning one-liner per model
.venv/bin/solm report               # full panel: dimensions, per-task, weak runs
.venv/bin/solm history --days 30    # composite trend with sparklines
.venv/bin/solm run                  # run the battery now (config trials)
.venv/bin/solm run --quick          # 1 trial, 3 tasks — fast pulse check
.venv/bin/solm daily                # battery + report + save + macOS notification
.venv/bin/solm schedule install     # launchd job, daily 05:45 (--at HH:MM to change)
.venv/bin/solm selftest             # prove every verifier against its reference solution
.venv/bin/solm doctor               # binaries, tasks, models, db
```

Setup from scratch: `uv venv .venv && uv pip install -e . --python .venv/bin/python`

## How a run works

1. Task fixture is copied to `~/.cache/state-of-llm/workspaces/<batch>/<model>/<task>-t<n>` and git-initialized.
2. The CLI runs headless in that workspace — claude with `--dangerously-skip-permissions`, codex with `--json --ephemeral -s workspace-write` (change in `config.toml [codex] sandbox`). Your live user config is inherited deliberately: this measures the daily driver, not the raw API.
3. The task's hidden `verify.py` (never copied into the workspace) scores the result 0–1 across mechanical checks.
4. The laziness scanner diffs workspace vs fixture and scans the final message.
5. Row lands in `data/state.db`; workspaces are kept 7 days for post-mortems (weak-run listings print the path).

## Config

`config.toml`: trials per task (default 2), concurrency (4), model list, binary
paths, codex sandbox. Add a model by appending a `[[models]]` block (any
model/effort combo the CLI accepts via `extra_args`).

## Adding a task

`tasks/<name>/` needs `task.toml` (prompt, timeout, dimension weights),
`fixture/` (what the agent sees), `verify.py` (hidden checks emitting
`{"score": 0..1, "checks": {...}}` JSON), and `solution/` (reference overlay
files). Then run `solm selftest` — it fails the task if the raw fixture already
passes or the solution doesn't score 1.0.

## Caveats

- Two trials per task is a signal, not a proof; a single YELLOW day means "verify", a multi-day slide means "believe it". The MAD band exists so ordinary variance doesn't cry wolf.
- Runs consume plan quota (~24 agent runs per daily battery). `--quick` exists for a cheap midday pulse.
- Scores compare a model **against its own history**, not model vs model — task difficulty is not calibrated across dimensions.
