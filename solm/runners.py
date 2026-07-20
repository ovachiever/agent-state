"""Adapters that drive the real coding CLIs headlessly.

Fidelity is the point: each adapter inherits your live user config (effort
level, personality, hooks) so the eval measures the tool you actually sit
down to use, not a lab-condition API call.
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
    status: str  # ok | error | timeout
    final_message: str = ""
    duration_s: float = 0.0
    turns: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    error: str = ""
    raw_files: list[str] = field(default_factory=list)


def _clean_env() -> dict:
    """Strip nested-session markers so headless children start clean."""
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("CLAUDECODE", "CLAUDE_CODE")):
            del env[key]
    return env


def _exec(cmd: list[str], cwd: Path, timeout: int, log_prefix: str) -> tuple[str, str, int | None, float, bool]:
    """Run a subprocess, tee stdout/stderr to workspace logs.

    Returns (stdout, stderr, returncode, duration_s, timed_out).
    """
    solm_dir = cwd / ".solm"
    solm_dir.mkdir(exist_ok=True)
    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=_clean_env(),
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

    def run(self, spec: ModelSpec, prompt: str, workspace: Path, timeout: int) -> RunResult:
        cmd = [
            self.bin,
            "-p", prompt,
            "--output-format", "json",
            "--dangerously-skip-permissions",
            "--max-turns", "60",
        ]
        if spec.model:
            cmd += ["--model", spec.model]
        cmd += spec.extra_args

        stdout, stderr, rc, duration, timed_out = _exec(cmd, workspace, timeout, "claude")
        if timed_out:
            return RunResult(status="timeout", duration_s=duration, error=f"timeout after {timeout}s")

        payload = self._parse_json(stdout)
        if payload is None:
            if rc != 0:
                return RunResult(status="error", duration_s=duration,
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
            error=str(payload.get("result", ""))[:500] if payload.get("is_error") else "",
        )

    @staticmethod
    def _parse_json(stdout: str) -> dict | None:
        text = stdout.strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
        # Fallback: last parseable JSON object line.
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

    def run(self, spec: ModelSpec, prompt: str, workspace: Path, timeout: int) -> RunResult:
        last_msg_path = workspace / ".solm" / "last_message.txt"
        (workspace / ".solm").mkdir(exist_ok=True)
        cmd = [
            self.bin, "exec",
            "--json",
            "--cd", str(workspace),
            "--skip-git-repo-check",
            "--ephemeral",
            "-s", self.sandbox,
            "-o", str(last_msg_path),
        ]
        if spec.model:
            cmd += ["-m", spec.model]
        cmd += spec.extra_args
        cmd.append(prompt)

        stdout, stderr, rc, duration, timed_out = _exec(cmd, workspace, timeout, "codex")
        if timed_out:
            return RunResult(status="timeout", duration_s=duration, error=f"timeout after {timeout}s")

        turns, input_tokens, output_tokens = self._parse_events(stdout)
        final_message = ""
        if last_msg_path.exists():
            final_message = last_msg_path.read_text(errors="replace")

        status = "ok" if rc == 0 else "error"
        return RunResult(
            status=status,
            final_message=final_message,
            duration_s=duration,
            turns=turns,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error="" if status == "ok" else f"codex exit {rc}: {stderr[-500:]}",
        )

    @staticmethod
    def _parse_events(stdout: str) -> tuple[int | None, int | None, int | None]:
        """Best-effort JSONL parse: count completed items, grab last token usage.

        Codex event shapes drift between versions, so nothing here is
        load-bearing — pass/fail comes from the verifier, not the transcript.
        """
        turns = 0
        input_tokens = output_tokens = None
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
            usage = event.get("usage")
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens", input_tokens)
                output_tokens = usage.get("output_tokens", output_tokens)
            info = event.get("info")
            if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
                tu = info["total_token_usage"]
                input_tokens = tu.get("input_tokens", input_tokens)
                output_tokens = tu.get("output_tokens", output_tokens)
        return (turns or None), input_tokens, output_tokens


def get_runner(cfg: Config, spec: ModelSpec):
    if spec.runner == "claude":
        return ClaudeRunner(cfg)
    if spec.runner == "codex":
        return CodexRunner(cfg)
    raise SystemExit(f"unknown runner '{spec.runner}' for model '{spec.name}'")
