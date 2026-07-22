"""Fingerprint the measurement instrument.

The eval inherits your live CLI configs by design. That means a config edit can
move scores without the model changing. The fingerprint pins what the yardstick
was for every batch, so the report can say "the ruler changed" instead of
letting a CLAUDE.md edit masquerade as model drift.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from agent_state.config import Config, TaskSpec


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _file_hash(path: Path) -> str:
    try:
        return _sha(path.read_text(errors="replace"))
    except OSError:
        return "absent"


def _bin_env(binary: str, extra: dict | None = None) -> dict:
    """Child env with the binary's own dir on PATH (launchd gives a bare PATH)."""
    import os

    env = dict(os.environ)
    env["PATH"] = f"{Path(binary).resolve().parent}:{env.get('PATH', '')}"
    if extra:
        env.update(extra)
    return env


def _version(binary: str) -> str:
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True,
                             timeout=15, env=_bin_env(binary))
        return out.stdout.strip() or out.stderr.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def _codex_auth(cfg: Config) -> str:
    """Auth mode of the eval codex home — a billing change is a yardstick change."""
    extra = {"CODEX_HOME": cfg.codex_home} if cfg.codex_home else None
    try:
        out = subprocess.run([cfg.codex_bin, "login", "status"], capture_output=True,
                             text=True, timeout=15, env=_bin_env(cfg.codex_bin, extra))
        return (out.stdout.strip() or out.stderr.strip())[:80]
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def _codex_config_hash() -> str:
    """Hash ~/.codex/config.toml minus volatile hook-trust state."""
    path = Path.home() / ".codex" / "config.toml"
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return "absent"
    text = re.sub(r'trusted_hash = "[^"]*"', "", text)
    return _sha(text)


def _claude_settings_summary() -> str:
    path = Path.home() / ".claude" / "settings.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return "absent"
    keys = {k: data.get(k) for k in ("model", "effortLevel", "alwaysThinkingEnabled") if k in data}
    return json.dumps(keys, sort_keys=True)


def collect(cfg: Config, tasks: list[TaskSpec]) -> dict:
    return {
        "claude_version": _version(cfg.claude_bin),
        "codex_version": _version(cfg.codex_bin),
        "codex_auth": _codex_auth(cfg),
        "claude_md": _file_hash(Path.home() / ".claude" / "CLAUDE.md"),
        "claude_settings": _claude_settings_summary(),
        "codex_config": _codex_config_hash(),
        "battery": {
            t.name: {"prompt": _sha(t.prompt), "weights": t.weights, "followups": len(t.followups)}
            for t in tasks
        },
    }


def diff(old: dict, new: dict) -> list[str]:
    """Human-readable list of what changed between two fingerprints."""
    changes = []
    for key in ("claude_version", "codex_version", "claude_md", "claude_settings", "codex_config"):
        if old.get(key) != new.get(key):
            changes.append(key)
    old_battery, new_battery = old.get("battery", {}), new.get("battery", {})
    added = set(new_battery) - set(old_battery)
    removed = set(old_battery) - set(new_battery)
    edited = {t for t in set(old_battery) & set(new_battery) if old_battery[t] != new_battery[t]}
    if added:
        changes.append(f"tasks added: {', '.join(sorted(added))}")
    if removed:
        changes.append(f"tasks removed: {', '.join(sorted(removed))}")
    if edited:
        changes.append(f"tasks edited: {', '.join(sorted(edited))}")
    return changes
