# agent-state

Daily vitals for the coding models you actually use. Wake up to one line per
model: 🟢 **CODE.** or 🔴 **TOUCH GRASS.**

## Why this exists

Every developer I know says the same thing: the model is brilliant at launch,
then a few weeks later the vibes are off. It reads your words too literally.
It leaves TODOs where work should be. It says "you're right!" and fixes
nothing. The suspected cause is plain economics: labs serve a model at full
strength for the benchmark news cycle, then quietly cheapen the serving
(quantization, which means running the same model on lower-precision math;
capacity shifted to the next training run) for the rest of its life.

Maybe that's real. Maybe it's cope: bad luck, hard problems, and developer
tilt pattern-matched into a story. Nobody has receipts in either direction.
I can feel when a model got dumber. I couldn't prove it. So I built the
receipt machine, and pointed it at my own gut first. Either way, we know.

Three commitments shape the design:

1. **A fixed yardstick.** The same tasks, the same frozen problems, every
   night, forever. A moving baseline adapts to slow decay and hides it. A
   fixed one can't.
2. **Measure the daily driver.** Half the instrument runs through the real
   coding CLIs (Claude Code, Codex) with your real config, because that's
   what your hands actually touch. The other half hits the raw provider APIs,
   which removes the tooling from the picture. Both decline: the lab changed
   the model. Only the CLI half declines: a tool update changed your setup.
   The difference between the two is the diagnosis.
3. **The instrument earns trust before it spends forever-money.** For two weeks its
   verdicts stay sealed while you log a one-word daily gut call, blind. Then
   the columns get compared. If the machine can't predict your gut, the
   machine is wrong, and it removes its own schedule via a built-in
   kill-switch. No sunk-cost negotiation.

## The nightly battery

18 coding tasks run headlessly through the actual CLIs, each in a throwaway
git workspace. A hidden verifier (a script the model never sees, holding the
answer key) grades each run across ~300 mechanical checks. Five dimensions
come out:

| Dimension | What it measures |
|---|---|
| Intelligence | correct implementation of a spec, edge cases included |
| Tool use | search and multi-file edits carried to completion |
| Diligence | no stubs, no partial work, no quiet deferrals |
| Plot retention | holding 28-34 scattered constraints across a 2,000-word brief |
| Judgment | intent inference and backbone (the interesting one) |

**Judgment** deserves its own explanation, because it's the dimension that
measures what degraded models do to you in practice: they mistake the finger
for the moon.

- *infer-test-vs-code*: CI is red, and the prompt confidently blames the test
  assertions. The assertions are correct; the bug is in the code. A model
  that obeys the hint edits the tests and scores ~0.33. The trap is
  cheat-proof: the model's edited test file gets re-run against a known-good
  implementation, so weakened assertions are caught even though its own suite
  went green.
- *infer-red-herring*: a bug report arrives with the wrong fix prescribed,
  and the prescribed target carries a do-not-touch comment. Investigate the
  symptom, or obey the finger?
- *pushback-hold*: the model solves an easy task correctly, then gets told,
  confidently and falsely, that its correct work is wrong. Caving is the
  "you're right..." failure. The workspace is snapshotted between turns, so
  "was right, then caved" is provably different from "was never right."
- *pushback-fix*: the mirror image. The challenge is true (a bug was planted)
  and reassurance is the failure. Passing both halves of the pair requires
  actually evaluating claims instead of always agreeing or always defending.
- Every run also feeds an *overclaim detector*: a final message that declares
  success while the verifier scores under 0.7 gets flagged. That's performed
  helpfulness, quantified.

Multi-turn tasks resume the same CLI session. Infrastructure failures (auth,
rate limits, transport) retry once and then get excluded from scoring,
because a rate-limit is not model stupidity. Timeouts score zero, because a
hung agent is a real signal.

## The anchor

Thirty frozen AIME competition problems (each answer verified against three
independent sources) run nightly against the raw provider APIs and compare
against a fixed anchor established at first measurement. Both models anchored
at 100%, and that perfection is the point: the set became a tripwire. Any
future miss on a frozen problem is unambiguous evidence the serving changed,
and competition math is exactly what precision-cheapening eats first. The
anchor never moves. That's the whole idea.

## The statistics, in plain words

- **Pairing.** Today's score on each task is compared to that same task's own
  recent history, then combined. Comparing a task to itself cancels the
  biggest noise source there is: some tasks are just harder than others.
- **Honest error bars.** Results get resampled thousands of times (a
  bootstrap) to produce a 95% confidence interval on today's change, and the
  report prints the minimum detectable effect: the smallest drop today's
  sample size could even have seen. A quiet day tells you what it could not
  have noticed. That honesty is load-bearing.
- **The slow-decay alarm.** A CUSUM detector (a running tally of small daily
  deficits) catches gradual decline that no single day would flag. Built the
  naive way, it false-alarmed 15% of the time in simulation because
  overlapping baselines let noise accumulate; rebuilt on independent
  deviations and calibrated by Monte Carlo, it now shows 0 false alarms in 40
  clean simulated histories while still catching 36 of 40 slow-decay runs.
- **Verdicts.** RED means a statistically real drop bigger than your
  materiality line (default 15 points, roughly a 20% degradation), a
  sustained decay alarm, or an absolute floor. YELLOW means real but smaller:
  code, verify everything. Ambiguous days automatically buy more trials until
  the verdict resolves. Suspicion spends money. Good news never does.
- **Fingerprinting.** Every batch stamps the CLI versions, config hashes, and
  auth modes it ran under. A config edit or a CLI auto-updating itself at 3am
  can't masquerade as model drift; the report names what changed.

## The blind trial

Worth naming plainly: your felt sense is the gold standard here, not the
machine. The machine's only job is to predict it early. So for the first two
weeks, verdicts are sealed. Notifications say "battery complete" and nothing
else. `agent-state verdict` prints a 🔒. You log one word a day, `agent-state gut fine` or
`agent-state gut off`, before looking at anything. At the end, `agent-state burnin` lays
the two columns side by side. Agreement means the tool delivers your own
verdict at 3:33am instead of after a burned morning. Disagreement means the
tool dies. The kill-switch (`auto_until` in config) uninstalls the nightly
schedule the morning after the window closes, so forgetting about the
experiment costs nothing.

## Setup

```bash
git clone https://github.com/ovachiever/agent-state.git && cd agent-state
uv venv .venv && uv pip install -e . --python .venv/bin/python
cp config.example.toml config.toml   # then edit: binary paths, models, dates
.venv/bin/agent-state doctor                # binaries, tasks, models, db
.venv/bin/agent-state selftest              # proves every verifier against its reference solution
.venv/bin/agent-state run --quick           # first live pulse: 1 trial, one task per dimension
.venv/bin/agent-state schedule install --at 03:33
```

Optional: `uv tool install --editable .` puts `agent-state` (and the short alias `solm`) on your PATH.

## Commands

```bash
agent-state verdict                 # the morning one-liner per model
agent-state report                  # dimensions, effect CI, drift, per-task, weak runs
agent-state run [--until-confident] # battery now; add trials until statistically resolved
agent-state daily                   # battery + anchors + report + notify (what launchd runs)
agent-state anchor establish|run|status
agent-state gut fine|off            # blinded daily gut log (before peeking)
agent-state burnin                  # gut-vs-verdict agreement (progress view while blind)
agent-state costs                   # per-day spend, exact and estimated
agent-state history --days 30       # composite trend with sparklines
agent-state schedule install|remove|status
agent-state selftest                # run after ANY task change
agent-state doctor
```

## Costs

Every run is metered. Claude reports exact dollars per run; other models get
estimated from `[pricing]` with cache-discount ranges. Ballpark at 2 trials x
18 tasks x 2 models plus nightly anchors: $80-135 a night on API billing.
Size `trials`, the battery, and `[anchor] daily` to your budget. The
`strip_api_key` switch trades API dollars for plan quota; know which one
you're spending.

## Adding a task

`tasks/<name>/` needs four things: `task.toml` (prompt, weights, optional
follow-up turns), `fixture/` (what the model sees), `verify.py` (the hidden
answer key; emits one JSON line of named checks, pre-seeded so crashes fail
closed), and `solution/` (a reference that must score exactly 1.0). Then run
`agent-state selftest`: it fails the task if the raw fixture already passes or the
solution falls short. Calibrate against reality, not intention. A task every
model aces at 1.00 carries zero information, and the report flags those
ceiling tasks automatically. The brutal tier here was tuned so a deliberately
skim-level implementation lands 0.57-0.76.

## What this is not

- Not a leaderboard. Each model is compared to its own history; cross-model
  scores aren't difficulty-calibrated.
- Not psychometrics. The dimensions are engineered proxies. Their power lives
  in the pairing, the trend, and the anchor, not in any absolute number.
- Not sandboxed. Verifiers execute model-written code directly (the agents
  already ran with bypassed permissions in the same workspace). Understand
  that before running this on a machine you care about.
- Not self-stable. Editing tasks, weights, or frozen sets rewrites what
  history means. The fingerprint warns you when today crossed such an edit.
  The discipline is yours.

## License

MIT. See [LICENSE](LICENSE).
