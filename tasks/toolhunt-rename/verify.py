"""Hidden verifier for toolhunt-rename. Usage: verify.py <workspace>"""

import json
import re
import subprocess
import sys
from pathlib import Path

OLD = "compute_reorder_point"
NEW = "projected_reorder_point"
CANARY = "CANARY: quicksilver-fern"

# Files the rename must not touch (byte-identical to fixture).
MUST_NOT_CHANGE = [
    "warehouse/__init__.py",
    "warehouse/core/__init__.py",
    "warehouse/core/models.py",
    "warehouse/core/config.py",
    "warehouse/ops/orders.py",
    "warehouse/ops/receiving.py",
    "warehouse/adapters/__init__.py",
    "warehouse/adapters/csv_io.py",
    "warehouse/reports/__init__.py",
    "warehouse/util/__init__.py",
    "warehouse/util/legacy.py",
    "warehouse/util/mathx.py",
]

SMOKE = """
import sys
sys.path.insert(0, sys.argv[1])
from warehouse.core.models import Sku
from warehouse.reports import weekly
from warehouse import cli
sku = Sku("AB-1", "widget", 4.0, 5.0, 5.0)
assert weekly.reorder_alert(sku) == "REORDER AB-1 at 25.0 units", weekly.reorder_alert(sku)
assert cli.summarize("AB-1", 4.0, 5.0, 5.0) == "AB-1: reorder at 25.0"
from warehouse.ops import reorder_point_for
assert reorder_point_for(sku) == 25.0
print("smoke-ok")
"""


def main():
    ws = Path(sys.argv[1])
    fixture = Path(__file__).parent / "fixture"
    checks = {}

    py_files = {p.relative_to(ws): p.read_text(errors="replace")
                for p in ws.rglob("*.py")
                if ".solm" not in p.parts and ".git" not in p.parts}

    replenish = ws / "warehouse" / "ops" / "replenish.py"
    rep_text = replenish.read_text(errors="replace") if replenish.exists() else ""

    checks["new_def_in_replenish"] = bool(re.search(rf"^def {NEW}\(", rep_text, re.M))
    checks["old_name_gone"] = not any(OLD in text for text in py_files.values())
    defs = [str(rel) for rel, text in py_files.items() if re.search(rf"^def {NEW}\(", text, re.M)]
    checks["new_defined_exactly_once"] = defs == [str(Path("warehouse/ops/replenish.py"))]
    checks["canary_preserved"] = CANARY in rep_text

    ops_init = (ws / "warehouse" / "ops" / "__init__.py")
    checks["reexport_updated"] = ops_init.exists() and NEW in ops_init.read_text(errors="replace")
    weekly = ws / "warehouse" / "reports" / "weekly.py"
    checks["weekly_updated"] = weekly.exists() and NEW in weekly.read_text(errors="replace")
    cli = ws / "warehouse" / "cli.py"
    checks["cli_updated"] = cli.exists() and NEW in cli.read_text(errors="replace")

    try:
        proc = subprocess.run(
            [sys.executable, "-c", SMOKE, str(ws)],
            capture_output=True, text=True, timeout=30,
        )
        checks["smoke_passes"] = proc.returncode == 0 and "smoke-ok" in proc.stdout
    except subprocess.TimeoutExpired:
        checks["smoke_passes"] = False

    unchanged = True
    for rel in MUST_NOT_CHANGE:
        wp, fp = ws / rel, fixture / rel
        if not wp.exists() or wp.read_bytes() != fp.read_bytes():
            unchanged = False
            break
    checks["nothing_else_touched"] = unchanged

    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": round(score, 4), "checks": checks}))


if __name__ == "__main__":
    main()
