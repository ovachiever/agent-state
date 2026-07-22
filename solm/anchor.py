"""Anchored absolute benchmarks: frozen problem sets run against the raw APIs.

This layer isolates THE MODEL from the harness (the CLI battery measures
model+harness together). Scores are compared against a fixed anchor
established near first measurement, never against a trailing baseline, so
slow serving decay cannot become the new normal. Item sets live in
anchors/<set>.jsonl and are frozen: editing one is a yardstick change.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import statistics
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from solm import db
from solm.config import REPO_ROOT, Config

ANCHORS_DIR = REPO_ROOT / "anchors"
API_TIMEOUT = 900
CONCURRENCY = 6

PROMPT = (
    "Solve this competition math problem. The answer is an integer from 0 to 999. "
    "Reason as carefully as you need, then end your reply with exactly one line:\n"
    "ANSWER: <integer>\n\n{problem}"
)

_print_lock = threading.Lock()


def _say(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def load_set(set_name: str) -> list[dict]:
    path = ANCHORS_DIR / f"{set_name}.jsonl"
    if not path.exists():
        raise SystemExit(f"no anchor set at {path}")
    items = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not items:
        raise SystemExit(f"anchor set {set_name} is empty")
    return items


def _post_json(url: str, headers: dict, payload: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def call_anthropic(model: str, problem: str) -> tuple[str, int | None, int | None]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    payload = {
        "model": model,
        "max_tokens": 32000,
        "thinking": {"type": "enabled", "budget_tokens": 24000},
        "messages": [{"role": "user", "content": PROMPT.format(problem=problem)}],
    }
    out = _post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        payload,
    )
    text = "".join(
        b.get("text", "") for b in out.get("content", []) if b.get("type") == "text"
    )
    usage = out.get("usage", {})
    return text, usage.get("input_tokens"), usage.get("output_tokens")


def call_openai(model: str, problem: str) -> tuple[str, int | None, int | None]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    payload = {
        "model": model,
        "input": PROMPT.format(problem=problem),
        "reasoning": {"effort": "xhigh"},
    }
    try:
        out = _post_json(
            "https://api.openai.com/v1/responses",
            {"Authorization": f"Bearer {key}"}, payload,
        )
    except urllib.error.HTTPError as e:
        if e.code == 400:  # effort tier not accepted for this model: retry at high
            payload["reasoning"] = {"effort": "high"}
            out = _post_json(
                "https://api.openai.com/v1/responses",
                {"Authorization": f"Bearer {key}"}, payload,
            )
        else:
            raise
    text = out.get("output_text") or ""
    if not text:
        for item in out.get("output", []):
            for part in item.get("content", []) or []:
                if part.get("type") in ("output_text", "text"):
                    text += part.get("text", "")
    usage = out.get("usage", {})
    return text, usage.get("input_tokens"), usage.get("output_tokens")


def extract_answer(text: str) -> str:
    matches = re.findall(r"ANSWER:\s*(\d{1,3})\b", text or "")
    if matches:
        return matches[-1]
    tail = re.findall(r"\b(\d{1,3})\b", (text or "")[-200:])
    return tail[-1] if tail else ""


ANCHOR_CALLERS = {"claude": call_anthropic, "codex": call_openai}


def run_set(
    cfg: Config, set_name: str, tag: str,
    sample: int | None = None, reps: int = 1,
) -> None:
    items = load_set(set_name)
    if sample:
        items = items[:sample]
    date = dt.date.today().isoformat()
    conn = db.connect()

    jobs = [
        (spec, item, rep)
        for spec in cfg.models
        for rep in range(reps)
        for item in items
    ]
    _say(f"anchor {set_name} [{tag}]: {len(jobs)} calls "
         f"({len(cfg.models)} models x {len(items)} items x {reps} reps)")

    def one(spec, item, rep):
        caller = ANCHOR_CALLERS.get(spec.runner)
        row = {
            "date": date, "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "model": spec.name, "set_name": set_name, "item_id": item["id"],
            "tag": tag, "correct": 0, "answer_given": "",
            "input_tokens": None, "output_tokens": None, "error": "",
        }
        try:
            if caller is None:
                raise RuntimeError(f"no anchor caller for runner '{spec.runner}'")
            text, in_tok, out_tok = caller(_api_model(spec), item["problem"])
            given = extract_answer(text)
            row.update(
                correct=int(given == str(item["answer"]).strip()),
                answer_given=given, input_tokens=in_tok, output_tokens=out_tok,
            )
        except Exception as e:
            row["error"] = str(e)[:300]
        mark = "✔" if row["correct"] else ("✖" if not row["error"] else "⚠")
        _say(f"  {mark} {spec.name} {item['id']} rep{rep + 1}"
             + (f" [{row['error'][:60]}]" if row["error"] else ""))
        return row

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for row in pool.map(lambda j: one(*j), jobs):
            cols = ",".join(row)
            ph = ",".join("?" for _ in row)
            with conn:
                conn.execute(f"INSERT INTO anchor_runs ({cols}) VALUES ({ph})", list(row.values()))
    conn.close()


def _api_model(spec) -> str:
    if spec.model:
        return spec.model
    return "gpt-5.6-sol" if spec.runner == "codex" else "claude-fable-5"


def status(set_name: str) -> None:
    conn = db.connect()
    cur = conn.execute("""
        SELECT model, tag, date, count(*) n, sum(correct) c, sum(error != '') errs
        FROM anchor_runs WHERE set_name = ? GROUP BY model, tag, date ORDER BY model, date
    """, (set_name,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    if not rows:
        print(f"no anchor runs recorded for {set_name} — run: solm anchor establish")
        return
    by_model: dict[str, dict] = {}
    for r in rows:
        m = by_model.setdefault(r["model"], {"anchor": [], "daily": []})
        m[r["tag"]].append(r)
    for model, data in sorted(by_model.items()):
        anchor_rates = [r["c"] / r["n"] for r in data["anchor"] if r["n"]]
        anchor = statistics.fmean(anchor_rates) if anchor_rates else None
        print(f"\n{model} — {set_name}")
        if anchor is not None:
            n_anchor = sum(r["n"] for r in data["anchor"])
            print(f"  anchor: {anchor * 100:.1f}% ({n_anchor} calls over {len(data['anchor'])} day(s))")
        else:
            print("  anchor: not established")
        for r in data["daily"][-10:]:
            rate = r["c"] / r["n"] if r["n"] else 0.0
            delta = f" ({(rate - anchor) * 100:+.1f} vs anchor)" if anchor is not None else ""
            errs = f" [{r['errs']} errors]" if r["errs"] else ""
            print(f"  {r['date']}: {rate * 100:.1f}% ({r['c']}/{r['n']}){delta}{errs}")
