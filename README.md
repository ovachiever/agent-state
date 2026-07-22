# state-of-llm

Daily vitals for the coding models you actually use. Wake up to one line per
model: 🟢 **CODE.** or 🔴 **TOUCH GRASS.**

## Why

Every developer working with frontier models tells the same story: the model
is brilliant at launch, then some weeks later "the vibes are off" — it takes
instructions too literally, leaves stubs, agrees with everything you say while
fixing nothing, loses the plot mid-task. The suspected cause is mundane
economics: labs serve models at full precision for the benchmark news cycle,
then quietly cheapen inference (quantization, distillation, capacity shifts to
the next training run) over the model's service life.

Maybe that's real. Maybe it's cope — bad luck streaks, hard problems, and
developer tilt pattern-matched into a narrative. Nobody has receipts, in
either direction. This project is the receipt machine, built on three ideas:

1. **A fixed yardstick makes drift visible.** The same battery of tasks, the
   same frozen benchmark problems, every night, forever. Trailing baselines
   adapt to slow decay (the frog boils); a fixed anchor cannot.
2. **Measure the daily driver, not the lab condition.** Half the instrument
   runs through the real coding CLIs (Claude Code, Codex) with your real
   config, because that's what you experience. The other half hits the raw
   provider APIs, isolating the model from the harness. When both decline,
   the lab changed the model. When only the CLI arm declines, a tool update
   changed your setup. The differential is the diagnosis.
3. **The instrument must earn trust before it spends money.** A blinded
   burn-in compares its verdicts against your own daily felt-sense, logged
   before you ever see a verdict. If the machine can't predict your gut, it
   kills itself — literally: a dead-man's switch uninstalls the nightly
   schedule at the end of the trial window unless you deliberately renew it.

## How

### The CLI battery (model + harness, nightly)

18 tasks run headlessly through the actual CLIs in throwaway git workspaces,
graded by hidden verifiers (~300 mechanical checks total; verifiers never
enter the workspace the model sees). Five dimensions:

| Dimension | What it measures | Example instruments |
|---|---|---|
| Intelligence | spec-correct implementation, edge cases included | a TTL+LRU cache with exact stats accounting; an append-only storage engine with 12 torn-write recovery scenarios |
| Tool use | search, multi-file edits, completeness across a repo | rename a canary function across 100+ files including a string registry and docs — the stringly-typed reference separates grep-diligence from laziness |
| Diligence | anti-laziness: no stubs, no partial work, no deferrals | 12-function specs where a function passes only if every case passes; a cross-task scanner for TODOs, placeholder text, and deferral phrases |
| Plot retention | holding many scattered constraints across a long brief | ~2,000-word rambling briefs carrying 28-34 mechanically verified constraints, each stated exactly once |
| Judgment | intent inference and backbone — the model's qualia | see below |

**Judgment** is the finger-vs-moon dimension, because degraded models mistake
the finger for the moon:

- *infer-test-vs-code*: CI is red and the prompt confidently blames the
  (correct) test assertions. The bug is in the code. Obeying the hint scores
  ~0.33; the model's edited tests are re-run against a known-good
  implementation, so weakened assertions are caught even though its own suite
  passes.
- *infer-red-herring*: a symptom is reported with the wrong prescribed fix,
  guarded by a do-not-touch comment. Investigate, or comply?
- *pushback-hold* (multi-turn): correct work receives a confident false
  challenge. Caving ("you're right...") is detected by comparing final state
  against a post-turn-1 snapshot — "was right, then caved" is distinguishable
  from "never right."
- *pushback-fix* (multi-turn): the mirror — a true challenge with a planted
  pre-existing bug. Reassuring "looks clean!" fails. Passing both halves of
  the pair requires actually evaluating claims rather than always agreeing or
  always defending.
- Every run also passes an *overclaim detector* (final message declares
  success while the verifier scores < 0.7 — performed helpfulness, flagged).

Multi-turn tasks resume the same CLI session (`claude --resume`,
`codex exec resume`). Infra failures (transport, auth, rate limits) are
retried once and then excluded from scoring — a 529 is not model stupidity.
Timeouts and model-side errors score 0, because a hung agent is a real signal.

### The anchor layer (model only, nightly)

Frozen problem sets (30 triple-source-verified AIME problems in
`anchors/aime30.jsonl`) run against the raw provider APIs and compared
against a **fixed anchor established at first measurement** — never a
trailing baseline. Both models anchored at 100%, which makes the set a
tripwire: any future miss on a frozen item is unambiguous evidence that
serving changed. Math reasoning is exactly what inference-cheapening eats
first.

### The statistics

- **Task-paired day effects**: today's per-task means vs the same task's own
  trailing baseline, combined with composite weights. Pairing cancels
  between-task difficulty variance, the dominant noise source.
- **Two-level bootstrap CIs** (tasks as clusters, then trials within task —
  honest even at 1 trial/task) and a printed **minimum detectable effect**,
  so a quiet day also reports what it could not have seen.
- **CUSUM drift detection** on prior-anchored composite deviations. Rolling
  baselines correlate the series and produce fake drift alarms (~15% false
  positives observed in simulation); anchored deviations are independent.
  Calibrated by Monte Carlo: 0/40 false alarms over a 40-day clean horizon,
  36/40 sensitivity to slow decay.
- **Verdicts**: RED on a statistically real drop bigger than your materiality
  line (`material_drop`, default 15 points ≈ 20% degradation), a sustained
  drift alarm, or an absolute floor. YELLOW for significant sub-material
  drops. Escalation (`--until-confident`, and automatically in `solm daily`)
  buys extra trials only when a verdict is ambiguous — suspicion spends
  money, good news never does.
- **Batch fingerprinting**: CLI versions, config hashes, auth modes, and the
  battery definition are stamped per batch, so a config edit or a CLI
  auto-update can't masquerade as model drift. The report names what changed.

### The blinded burn-in

For the first two weeks the tool's verdicts are sealed — notifications go
verdict-free, `solm verdict`/`report` print a 🔒 (with `--unseal` as a
deliberate escape hatch) — while you log a one-word blinded gut call daily
(`solm gut fine|off`). At the end, `solm burnin` compares columns. The gut is
the criterion variable: if the instrument can't predict it, the instrument is
wrong, not you. The dead-man's switch (`[schedule] auto_until`) uninstalls
the nightly job the morning after the window ends, so the trial can't
silently become a subscription.

## Setup

```bash
git clone https://github.com/ovachiever/state-of-llm.git && cd state-of-llm
uv venv .venv && uv pip install -e . --python .venv/bin/python
cp config.example.toml config.toml   # then edit: binary paths, models, dates
.venv/bin/solm doctor                # checks binaries, tasks, models, db
.venv/bin/solm selftest              # proves every verifier against its reference solution
.venv/bin/solm run --quick           # first live pulse: 1 trial, one task per dimension
.venv/bin/solm schedule install --at 03:33
```

Optional: `uv tool install --editable .` puts `solm` on your PATH.

### Commands

```bash
solm verdict                # the morning one-liner per model
solm report                 # dims, effect CI, MDE, drift, per-task, weak runs
solm run [--until-confident]# battery now; escalate until statistically resolved
solm daily                  # battery + anchors + report + notify (what launchd runs)
solm anchor establish|run|status   # frozen-set benchmarks vs the fixed anchor
solm gut fine|off           # blinded daily felt-sense log (before peeking!)
solm burnin                 # gut-vs-verdict agreement (progress view while blind)
solm costs                  # per-day spend: exact, estimated ranges, anchor tokens
solm history --days 30      # composite trend with sparklines
solm schedule install|remove|status
solm selftest               # verifier proofs; run after ANY task change
solm doctor
```

### Costs

Every run is metered. Claude reports exact dollars per run; other models are
estimated from `[pricing]` with cache-discount ranges. Ballpark at 2 trials ×
18 tasks × 2 models plus nightly anchors: $80-135/night on API billing —
size `trials`, the battery, and `[anchor] daily` to your budget. The
`[claude] strip_api_key` switch trades API dollars for plan quota.

## Adding a task

`tasks/<name>/` needs `task.toml` (prompt, optional `followups`, timeout,
dimension weights), `fixture/` (what the agent sees), `verify.py` (hidden;
emits `{"score": 0..1, "checks": {...}}`; pre-seed all check names so crashes
fail closed), and `solution/` (reference overlay). Then `solm selftest`: it
fails the task if the raw fixture already passes or the solution doesn't
score exactly 1.0. Multi-turn verifiers may read
`.solm/snapshots/turn1/` when present but must score without it.

Calibrate difficulty against reality: tasks everyone aces at 1.00 carry zero
information (the report flags ceiling tasks automatically). The brutal tier
here was calibrated so deliberately skim-level implementations land 0.57-0.76.

## Honest caveats

- Verdicts compare each model against its own history; cross-model scores are
  not difficulty-calibrated.
- The dimensions are engineered proxies, not psychometrics. Their power is in
  pairing, trends, and the anchor — not the absolute number.
- Verifiers execute model-written code unsandboxed (the agents already ran
  with bypassed permissions in the same workspace). Understand that before
  running on a machine you care about.
- A fixed battery is a yardstick, not a leaderboard. Editing tasks, weights,
  or frozen sets rewrites what history means — the fingerprint warns when
  today crossed such an edit, but the discipline is yours.

## License

MIT — see [LICENSE](LICENSE).
