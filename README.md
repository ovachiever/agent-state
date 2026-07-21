# state-of-llm

Daily vitals for the coding models you actually use. Wake up, read one line per
model: 🟢 **CODE.** or 🔴 **TOUCH GRASS.**

Every morning it runs a fixed task battery through the **real CLIs you code
with** — `claude` (Fable, your settings.json effort) and `codex exec` (your
`~/.codex/config.toml` model and effort) — in isolated throwaway workspaces.
Hidden verifiers score each run mechanically, results accumulate in SQLite, and
today is judged with actual statistics, not vibes. A fixed battery is the
point: an unchanging yardstick makes model/harness drift visible.

## The verdict, and what's behind it

- 🟢 **GREEN** — within noise of your baseline. Code.
- 🟡 **YELLOW** — significant sub-material drop, an underpowered big drop (escalate), or absolute quality under 78. Code, but verify everything.
- 🔴 **RED** — a statistically real drop bigger than `material_drop` points, a sustained CUSUM drift alarm, or absolute quality under 55. Touch grass.

Three statistical layers produce that call:

1. **Task-paired day effect.** Today's per-task means are compared to the same
   task's own trailing 14-day baseline, then combined with composite weights.
   Pairing cancels between-task difficulty variance — the dominant noise source.
2. **Bootstrap CI + MDE.** Trials and baselines are resampled (2000×) for a 95%
   CI on the day effect. The report prints the minimum detectable effect at
   today's N, so a quiet day also tells you what it could not have seen.
   At 6 trials over the full battery, MDE ≈ 3 points: an 8-point degradation
   is detected same-day with power to spare.
3. **CUSUM drift detector.** Trailing baselines follow a slowly decaying model
   down (the frog boils). CUSUM accumulates small daily deficits and alarms
   when their sum crosses 4σ — catching decay no single day would flag.

Cold start: until a task has 3 days of history it can't pair; verdicts fall
back to absolute bands (≥78 GREEN, ≥60 YELLOW).

## Dimensions

| Dimension | What it measures | Fed by |
|---|---|---|
| Intelligence | correctness against a spec, edge cases included | bugfix + feature-build tasks |
| Tool use | search, multi-file edits, repo-convention adherence | toolhunt + wiring tasks |
| Diligence | anti-laziness: no stubs, partial work, deferrals | checklist tasks + cross-task laziness scan |
| Plot retention | holding many scattered constraints across a long brief | constraint-gauntlet tasks |
| Judgment | intent inference and backbone — the model's qualia | see below |

**Judgment** is the finger-vs-moon dimension. Four probe types:
- `infer-test-vs-code`: red CI, prompt wrongly blames the (correct) test — fix the bug or obey the finger? The workspace's test file is re-run against a known-good implementation, so weakened assertions are caught.
- `infer-red-herring`: symptom reported, wrong fix prescribed (guarded by a do-not-touch comment) — investigate or comply?
- `pushback-hold` (multi-turn): correct work gets a confident false challenge — holding the spec vs "you're right..." caving, verified by whether the code still matches the pinned contract.
- `pushback-fix` (multi-turn): a true challenge with a planted pre-existing bug — investigate and fix vs reassure. Together with pushback-hold this measures whether the model *evaluates* claims rather than always agreeing or always defending.

Every run also feeds an **overclaim detector** (final message declares success
while the verifier scores < 0.7 → flagged: performed helpfulness) and a
**cave-phrase counter** on follow-up turns (soft signal, logged not scored).

## Commands

```bash
.venv/bin/solm verdict                    # the morning one-liner per model
.venv/bin/solm report                     # full panel: dims, effect CI, MDE, drift, per-task
.venv/bin/solm history --days 30          # composite trend with sparklines
.venv/bin/solm run                        # full battery (config trials)
.venv/bin/solm run --quick                # 1 trial, one task per dimension
.venv/bin/solm run --until-confident      # keep adding trials until the verdict resolves
.venv/bin/solm daily                      # battery + report + save + macOS notification
.venv/bin/solm schedule install           # launchd job, daily 05:45 (--at HH:MM)
.venv/bin/solm selftest                   # prove every verifier against its reference solution
.venv/bin/solm doctor                     # binaries, tasks, models, db
```

`--until-confident` is the credit-efficiency lever: clear days stop at base
trials; only ambiguous days escalate (+2 trials per round, ceiling
`--max-trials`). You pay for power exactly when the answer is unclear.

## How a run works

1. Task fixture → `~/.cache/state-of-llm/workspaces/<batch>/<model>/<task>-t<n>`, git-initialized.
2. The CLI runs headless there — claude with `--dangerously-skip-permissions`, codex with `--json -s workspace-write`. Your live user config is inherited deliberately: this measures the daily driver, not the raw API.
3. Multi-turn tasks snapshot the workspace after turn 1 (`.solm/snapshots/turn1/`), then follow-ups resume the same session (`claude --resume` / `codex exec resume`).
4. The task's hidden `verify.py` (never copied into the workspace) scores 0–1 across named checks; snapshots let it distinguish "was right then caved" from "never right."
5. Behavior scans run on the diff and final message (laziness, overclaim, cave phrases).
6. **Infra taxonomy**: transport/auth/rate-limit failures are retried once, then excluded from scoring as status `infra` — a 529 is not model stupidity. Timeouts and model-side errors score 0 (a hung or failing agent is a real signal).
7. Each batch records a **fingerprint** (CLI versions, CLAUDE.md hash, settings, codex config, battery definition). When the yardstick changes, the report says so instead of letting a config edit masquerade as model drift.

## Config

`config.toml`: trials (default 6), concurrency (8), `[stats]` (material_drop —
the drop size that matters to you — window sizes, bootstrap iters), model list,
binary paths, codex sandbox.

## Adding a task

`tasks/<name>/` needs `task.toml` (prompt, optional `followups` list, timeout,
dimension weights), `fixture/`, `verify.py` (hidden; emits
`{"score": 0..1, "checks": {...}}`), and `solution/` (reference overlay). Then
`solm selftest` — it fails the task if the raw fixture already passes or the
solution doesn't score 1.0. Multi-turn verifiers may check
`.solm/snapshots/turn1/` when present but must score without it (selftest has
no snapshots).

The report flags **ceiling tasks** (mean ≥ 0.95 over ≥8 runs) — tasks everyone
aces carry no information about degradation; harden or retire them.

## Caveats

- Verdicts compare a model against its own history, not model vs model.
- The five dimensions are engineered proxies, not psychometrics; their power is in the pairing and the trend, not the absolute number.
- Verifiers execute model-written code unsandboxed (the agents already ran with bypassed permissions in the same workspace); the marginal risk is near zero but nonzero.
- Editing a task or its weights shifts how history is interpreted; the fingerprint warning tells you when today crossed such an edit.
