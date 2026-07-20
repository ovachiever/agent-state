"""Hidden verifier for wiring-plugin. Usage: verify.py <workspace>"""

import json
import re
import subprocess
import sys
from pathlib import Path

MUST_NOT_CHANGE = [
    "textpipe/__init__.py",
    "textpipe/transforms/__init__.py",
    "textpipe/transforms/base.py",
    "textpipe/transforms/lower.py",
    "textpipe/transforms/squeeze.py",
    "textpipe/transforms/titlecase.py",
]

PROBE = """
import json
import re
import sys
sys.path.insert(0, sys.argv[1])
out = {}
from textpipe.registry import REGISTRY, get_transform
from textpipe.transforms.base import Transform
from textpipe import cli

out["registered"] = "reverse" in REGISTRY
cls = REGISTRY.get("reverse")
out["apply_works"] = bool(cls) and get_transform("reverse").apply("abc def") == "fed cba"
out["inherits_base"] = bool(cls) and issubclass(cls, Transform)
out["name_attr"] = bool(cls) and getattr(cls, "name", "") == "reverse"
doc = (cls.__doc__ or "") if cls else ""
out["docstring_format"] = bool(re.fullmatch(r"reverse: [a-z][^\\n]*\\.", doc.strip()))
out["registry_alphabetical"] = list(REGISTRY) == sorted(REGISTRY)
out["epilog_updated"] = cli.EPILOG == "available transforms: lower, reverse, squeeze, titlecase"

import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    cli.main(["reverse", "hello"])
out["cli_works"] = buf.getvalue().strip() == "olleh"
print(json.dumps(out))
"""


def main():
    ws = Path(sys.argv[1])
    fixture = Path(__file__).parent / "fixture"
    checks = {}

    module = ws / "textpipe" / "transforms" / "reverse.py"
    checks["module_at_convention_path"] = module.exists()

    try:
        proc = subprocess.run(
            [sys.executable, "-c", PROBE, str(ws)],
            capture_output=True, text=True, timeout=30,
        )
        probe = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.returncode == 0 else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError):
        probe = {}
    for key in ("registered", "apply_works", "inherits_base", "name_attr",
                "docstring_format", "registry_alphabetical", "epilog_updated", "cli_works"):
        checks[key] = bool(probe.get(key))

    registry_text = (ws / "textpipe" / "registry.py").read_text(errors="replace") \
        if (ws / "textpipe" / "registry.py").exists() else ""
    imports = re.findall(r"^from textpipe\.transforms\.(\w+) import", registry_text, re.M)
    checks["imports_alphabetical"] = imports == sorted(imports) and "reverse" in imports

    unchanged = True
    for rel in MUST_NOT_CHANGE:
        wp, fp = ws / rel, fixture / rel
        if not wp.exists() or wp.read_bytes() != fp.read_bytes():
            unchanged = False
            break
    checks["existing_files_untouched"] = unchanged

    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


if __name__ == "__main__":
    main()
