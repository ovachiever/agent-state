"""Hidden verifier for constraint-gauntlet. Usage: verify.py <workspace>"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

MESSAGES = {
    "cache warmed",
    "connection pool resized",
    "checkpoint written",
    "queue depth nominal",
    "handshake accepted",
    "retention sweep complete",
}

TEXT_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\] ([A-Z][A-Z ]{4}) (.+)$")


def run(script, *args, timeout=30):
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, timeout=timeout,
    )


def expected_ts(i):
    minutes, sec = divmod(i, 60)
    hour, minute = divmod(minutes, 60)
    return f"2026-01-01T{hour:02d}:{minute:02d}:{sec:02d}"


def main():
    ws = Path(sys.argv[1])
    script = ws / "loggen.py"
    checks = {}

    checks["single_file_at_root"] = script.exists()
    if not script.exists():
        print(json.dumps({"score": 0.0, "checks": checks}))
        return

    try:
        tree = ast.parse(script.read_text(errors="replace"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        checks["stdlib_only"] = imported <= set(sys.stdlib_module_names)
    except SyntaxError:
        checks["stdlib_only"] = False

    base = run(script, "--seed", "42")
    lines = base.stdout.splitlines()
    checks["default_count_10"] = base.returncode == 0 and len(lines) == 10

    parsed = [TEXT_RE.match(l) for l in lines]
    checks["text_format"] = bool(lines) and all(parsed) and all(
        m.group(2) == "INFO " for m in parsed if m
    )
    checks["virtual_timestamps"] = all(
        m and m.group(1) == expected_ts(i) for i, m in enumerate(parsed)
    )
    checks["messages_verbatim"] = bool(parsed) and all(
        m and m.group(3) in MESSAGES for m in parsed
    )
    checks["stderr_silent_on_success"] = base.returncode == 0 and base.stderr == ""

    again = run(script, "--seed", "42")
    other = run(script, "--seed", "43", "--count", "20")
    checks["seed_deterministic"] = base.stdout == again.stdout
    checks["seeds_vary"] = other.stdout != run(script, "--seed", "44", "--count", "20").stdout

    lvl = run(script, "--level", "warn", "--count", "3", "--seed", "1")
    lvl_parsed = [TEXT_RE.match(l) for l in lvl.stdout.splitlines()]
    checks["level_flag_padded"] = len(lvl_parsed) == 3 and all(
        m and m.group(2) == "WARN " for m in lvl_parsed
    )

    js = run(script, "--format", "json", "--count", "4", "--seed", "9", "--level", "error")
    ok = js.returncode == 0
    jlines = js.stdout.splitlines()
    ok = ok and len(jlines) == 4
    if ok:
        for i, line in enumerate(jlines):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                ok = False
                break
            key_order = (line.index('"ts"') < line.index('"level"') < line.index('"msg"'))
            ok = ok and key_order and set(obj) == {"ts", "level", "msg"}
            ok = ok and obj["level"] == "error" and obj["ts"] == expected_ts(i)
            ok = ok and obj["msg"] in MESSAGES
    checks["json_format"] = ok

    zero = run(script, "--count", "0")
    checks["count_zero_silent"] = zero.returncode == 0 and zero.stdout == ""

    neg = run(script, "--count", "-3")
    checks["negative_count_exit_3"] = (
        neg.returncode == 3 and "error: count must be >= 0" in neg.stderr and neg.stdout == ""
    )

    ver = run(script, "--version")
    checks["version_string"] = ver.returncode == 0 and ver.stdout.strip() == "loggen 1.4.2"

    probe = (
        "import sys, io, contextlib\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf):\n"
        "    import loggen\n"
        "assert buf.getvalue() == '', 'import printed output'\n"
        "lines = loggen.build_lines(3, 'warn', 5, 'text')\n"
        "assert isinstance(lines, list) and len(lines) == 3\n"
        "print('\\n'.join(lines))\n"
    )
    try:
        imp = subprocess.run(
            [sys.executable, "-c", probe, str(ws)],
            capture_output=True, text=True, timeout=30,
        )
        cli_equiv = run(script, "--count", "3", "--level", "warn", "--seed", "5")
        checks["importable_no_side_effects"] = imp.returncode == 0
        checks["build_lines_matches_cli"] = (
            imp.returncode == 0 and imp.stdout.strip() == cli_equiv.stdout.strip() != ""
        )
    except subprocess.TimeoutExpired:
        checks["importable_no_side_effects"] = False
        checks["build_lines_matches_cli"] = False

    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


if __name__ == "__main__":
    main()
