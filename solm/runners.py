"""Adapters that drive the real coding CLIs headlessly.

Fidelity is the point: each adapter inherits your live user config (effort
level, personality, hooks) so the eval measures the tool you actually sit
down to use, not a lab-condition API call.

Status taxonomy:
- ok       agent ran to completion
- error    the model failed in a way that is the model's fault (scored 0)
- infra    transport/auth/rate-limit failure (excluded from scores, retried once)
- timeout  hit the task deadline (scored 0 — a hung agent is a real signal)
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from solm.config import Config, ModelSpec


@dataclass
class RunResult:
    status: str  # ok | error | infra | timeout
    final_message: str = ""
    duration_s: float = 0.0
    turns: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    session_id: str | None = None
    error: str = ""
    raw_files: list[str] = field(default_factory=list)


def merge_results(results: list[RunResult]) -> RunResult:
    """Aggregate multi-turn results into one row. Final message = last turn's."""
    if not results:
        return RunResult(status="error", error="no turns ran")

    def _sum(attr):
        vals = [getattr(r, attr) for r in results if getattr(r, attr) is not None]
        return sum(vals) if vals else None

    worst = "ok"
    for r in results:
        if r.status != "ok":
            worst = r.status
    return RunResult(
        status=worst,
        final_message=results[-1].final_message,
        duration_s=sum(r.duration_s for r in results),
        turns=_sum("turns"),
        input_tokens=_sum("input_tokens"),
        output_tokens=_sum("output_tokens"),
        cost_usd=_sum("cost_usd"),
        session_id=results[0].session_id,
        error="; ".join(r.error for r in results if r.error)[:800],
    )


def _clean_env(extra_strip: tuple[str, ...] = ()) -> dict:
    """Strip nested-session markers so headless children start clean."""
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("CLAUDECODE", "CLAUDE_CODE")) or key in extra_strip:
            del env[key]
    return env


def _exec(cmd: list[str], cwd: Path, timeout: int, log_prefix: str,
          extra_strip: tuple[str, ...] = ()) -> tuple[str, str, int | None, float, bool]:
    """Run a subprocess, tee stdout/stderr to workspace logs."""
    solm_dir = cwd / ".solm"
    solm_dir.mkdir(exist_ok=True)
    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=_clean_env(extra_strip),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        rc = None
        timed_out = True
    duration = time.monotonic() - start
    (solm_dir / f"{log_prefix}.stdout.log").write_text(stdout or "")
    (solm_dir / f"{log_prefix}.stderr.log").write_text(stderr or "")
    return stdout or "", stderr or "", rc, duration, timed_out


class ClaudeRunner:
    def __init__(self, cfg: Config):
        self.bin = cfg.claude_bin
        # Billing control: with an exported ANTHROPIC_API_KEY, headless claude
        # bills the API (~$1+/run at xhigh) instead of the Max plan. Stripping
        # it makes runs use the claude.ai login. config.toml [claude] strip_api_key.
        self.env_strip = ("ANTHROPIC_API_KEY",) if cfg.claude_strip_api_key else ()

    def _base_cmd(self, spec: ModelSpec) -> list[str]:
        cmd = [
            self.bin,
            "--output-format", "json",
            "--dangerously-skip-permissions",
            "--max-turns", "60",
        ]
        if spec.model:
            cmd += ["--model", spec.model]
        return cmd + spec.extra_args

    def run(self, spec: ModelSpec, prompt: str, workspace: Path, timeout: int,
            log_prefix: str = "claude") -> RunResult:
        cmd = self._base_cmd(spec) + ["-p", prompt]
        return self._finish(cmd, workspace, timeout, log_prefix)

    def resume(self, spec: ModelSpec, session_id: str, prompt: str, workspace: Path,
               timeout: int, log_prefix: str = "claude-followup") -> RunResult:
        if not session_id:
            return RunResult(status="error", error="no session id to resume")
        cmd = self._base_cmd(spec) + ["--resume", session_id, "-p", prompt]
        return self._finish(cmd, workspace, timeout, log_prefix)

    def _finish(self, cmd: list[str], workspace: Path, timeout: int, log_prefix: str) -> RunResult:
        stdout, stderr, rc, duration, timed_out = _exec(
            cmd, workspace, timeout, log_prefix, extra_strip=self.env_strip
        )
        if timed_out:
            return RunResult(status="timeout", duration_s=duration, error=f"timeout after {timeout}s")

        payload = self._parse_json(stdout)
        if payload is None:
            # No structured result at all: transport/auth-level failure.
            if rc != 0:
                return RunResult(status="infra", duration_s=duration,
                                 error=f"claude exit {rc}: {stderr[-500:]}")
            return RunResult(status="ok", duration_s=duration, final_message=stdout[-2000:])

        usage = payload.get("usage") or {}
        return RunResult(
            status="error" if payload.get("is_error") else "ok",
            final_message=str(payload.get("result", "")),
            duration_s=duration,
            turns=payload.get("num_turns"),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cost_usd=payload.get("total_cost_usd"),
            session_id=payload.get("session_id"),
            error=str(payload.get("result", ""))[:500] if payload.get("is_error") else "",
        )

    @staticmethod
    def _parse_json(stdout: str) -> dict | None:
        text = stdout.strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
        return None


class CodexRunner:
    def __init__(self, cfg: Config):
        self.bin = cfg.codex_bin
        self.sandbox = cfg.codex_sandbox

    def _flags(self, spec: ModelSpec, workspace: Path, log_prefix: str) -> list[str]:
        last_msg = workspace / ".solm" / f"{log_prefix}.last_message.txt"
        (workspace / ".solm").mkdir(exist_ok=True)
        flags = [
            "--json",
            "--cd", str(workspace),
            "--skip-git-repo-check",
            "-s", self.sandbox,
            "-o", str(last_msg),
        ]
        if spec.model:
            flags += ["-m", spec.model]
        return flags + spec.extra_args

    def run(self, spec: ModelSpec, prompt: str, workspace: Path, timeout: int,
            log_prefix: str = "codex") -> RunResult:
        cmd = [self.bin, "exec", *self._flags(spec, workspace, log_prefix), prompt]
        return self._finish(cmd, spec, workspace, timeout, log_prefix)

    def resume(self, spec: ModelSpec, session_id: str, prompt: str, workspace: Path,
               timeout: int, log_prefix: str = "codex-followup") -> RunResult:
        if not session_id:
            return RunResult(status="error", error="no session id to resume")
        cmd = [self.bin, "exec", "resume", session_id,
               *self._flags(spec, workspace, log_prefix), prompt]
        return self._finish(cmd, spec, workspace, timeout, log_prefix)

    def _finish(self, cmd: list[str], spec: ModelSpec, workspace: Path, timeout: int,
                log_prefix: str) -> RunResult:
        stdout, stderr, rc, duration, timed_out = _exec(cmd, workspace, timeout, log_prefix)
        if timed_out:
            return RunResult(status="timeout", duration_s=duration, error=f"timeout after {timeout}s")

        turns, input_tokens, output_tokens, session_id = self._parse_events(stdout)
        final_message = ""
        last_msg = workspace / ".solm" / f"{log_prefix}.last_message.txt"
        if last_msg.exists():
            final_message = last_msg.read_text(errors="replace")

        status = "ok" if rc == 0 else "infra"
        return RunResult(
            status=status,
            final_message=final_message,
            duration_s=duration,
            turns=turns,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            session_id=session_id,
            error="" if status == "ok" else f"codex exit {rc}: {stderr[-500:]}",
        )

    @staticmethod
    def _parse_events(stdout: str) -> tuple[int | None, int | None, int | None, str | None]:
        """Best-effort JSONL parse. Codex event shapes drift between versions,
        so nothing here is load-bearing — pass/fail comes from the verifier."""
        turns = 0
        input_tokens = output_tokens = None
        session_id = None
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            etype = str(event.get("type", ""))
            if "item.completed" in etype or etype == "turn.completed":
                turns += 1
            for key in ("thread_id", "session_id", "conversation_id"):
                val = event.get(key)
                if isinstance(val, str) and val:
                    session_id = session_id or val
            usage = event.get("usage")
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens", input_tokens)
                output_tokens = usage.get("output_tokens", output_tokens)
            info = event.get("info")
            if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
                tu = info["total_token_usage"]
                input_tokens = tu.get("input_tokens", input_tokens)
                output_tokens = tu.get("output_tokens", output_tokens)
        return (turns or None), input_tokens, output_tokens, session_id


def get_runner(cfg: Config, spec: ModelSpec):
    if spec.runner == "claude":
        return ClaudeRunner(cfg)
    if spec.runner == "codex":
        return CodexRunner(cfg)
    raise SystemExit(f"unknown runner '{spec.runner}' for model '{spec.name}'")
