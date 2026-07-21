"""Hidden verifier for gauntlet-config-merge. Usage: verify.py <workspace>

All JSON inputs are written to a private temp dir at verify time — the fixture
sample files are for the agent's benefit only and are never trusted here,
because the agent can edit them.
"""

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = {
    "service": {
        "name": "orders",
        "port": 8080,
        "tls": {"enabled": False, "cert": "/etc/ssl/orders.pem"},
    },
    "features": ["audit", "metrics", "tracing"],
    "zeta": 1,
    "greeting": "café",
}
ENV = {
    "service": {"port": 9090, "tls": {"enabled": True}},
    "features": ["audit"],
    "steps": ["init", "$delete", "run"],
    "zeta": "$delete",
    "ghost": "$delete",
}
LOCAL = {
    "service": {"tls": {"cert": "$delete"}},
    "owner": "platform",
}


ALL_CHECKS = [
    "single_file_at_root", "stdlib_only", "deep_merge_objects", "scalar_override",
    "arrays_replace", "delete_sentinel_top", "delete_sentinel_nested",
    "delete_literal_in_arrays", "sorted_keys_all_levels", "two_space_indent",
    "trailing_newline", "utf8_passthrough", "stderr_silent_on_success",
    "single_layer_canonical", "lenient_conflict_replaces", "strict_conflict_contract",
    "strict_bool_not_number", "strict_delete_exempt", "missing_file_contract",
    "invalid_json_contract", "toplevel_not_object_contract", "version_string",
    "importable_no_side_effects", "merge_configs_matches_cli",
]


def write_layers(tmp, **files):
    for name, obj in files.items():
        (tmp / f"{name}.json").write_text(
            obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8"
        )


def run(script, tmp, *args, timeout=30):
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, timeout=timeout, cwd=str(tmp),
    )


def levels_sorted(stdout):
    ok = [True]

    def hook(pairs):
        keys = [k for k, _ in pairs]
        if keys != sorted(keys):
            ok[0] = False
        return dict(pairs)

    try:
        json.loads(stdout, object_pairs_hook=hook)
    except (json.JSONDecodeError, ValueError):
        return False
    return ok[0]


def main():
    checks = {}
    try:
        run_checks(checks)
    except Exception:
        pass
    if checks.get("single_file_at_root"):
        # A crash/hang partway through must fail the unreached checks, not
        # drop them from the mean.
        for name in ALL_CHECKS:
            checks.setdefault(name, False)
    score = (sum(checks.values()) / len(checks)) if checks else 0.0
    print(json.dumps({"score": round(score, 4), "checks": checks}))


def run_checks(checks):
    ws = Path(sys.argv[1]).resolve()
    script = ws / "cfgmerge.py"

    checks["single_file_at_root"] = script.exists()
    if not script.exists():
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

    with tempfile.TemporaryDirectory(prefix="cfgmerge-verify-") as raw:
        tmp = Path(raw)
        write_layers(tmp, base=BASE, env=ENV, local=LOCAL)

        big = run(script, tmp, "base.json", "env.json", "local.json")
        try:
            obj = json.loads(big.stdout)
        except (json.JSONDecodeError, ValueError):
            obj = None

        svc = obj.get("service", {}) if isinstance(obj, dict) else {}
        tls = svc.get("tls", {}) if isinstance(svc, dict) else {}
        checks["deep_merge_objects"] = (
            big.returncode == 0
            and svc.get("name") == "orders"
            and tls.get("enabled") is True
        )
        checks["scalar_override"] = svc.get("port") == 9090
        checks["arrays_replace"] = isinstance(obj, dict) and obj.get("features") == ["audit"]
        checks["delete_sentinel_top"] = (
            isinstance(obj, dict) and "zeta" not in obj and "ghost" not in obj
        )
        checks["delete_sentinel_nested"] = isinstance(tls, dict) and "cert" not in tls
        checks["delete_literal_in_arrays"] = (
            isinstance(obj, dict) and obj.get("steps") == ["init", "$delete", "run"]
        )
        checks["sorted_keys_all_levels"] = bool(big.stdout) and levels_sorted(big.stdout)
        indents = [
            len(line) - len(line.lstrip(" "))
            for line in big.stdout.splitlines()
            if line.strip()
        ]
        checks["two_space_indent"] = (
            "\t" not in big.stdout
            and bool(indents)
            and all(n % 2 == 0 for n in indents)
            and 2 in indents
            and 4 in indents
        )
        checks["trailing_newline"] = big.stdout.endswith("\n") and not big.stdout.endswith("\n\n")
        checks["utf8_passthrough"] = "café" in big.stdout and "\\u" not in big.stdout
        checks["stderr_silent_on_success"] = big.returncode == 0 and big.stderr == ""

        single = run(script, tmp, "base.json")
        canonical = json.dumps(BASE, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        checks["single_layer_canonical"] = single.returncode == 0 and single.stdout == canonical

        write_layers(
            tmp,
            lenient_a={"db": {"host": "x"}, "port": 8080},
            lenient_b={"db": "postgres://prod", "port": "8080"},
        )
        lenient = run(script, tmp, "lenient_a.json", "lenient_b.json")
        try:
            lob = json.loads(lenient.stdout)
        except (json.JSONDecodeError, ValueError):
            lob = {}
        checks["lenient_conflict_replaces"] = (
            lenient.returncode == 0
            and lob.get("db") == "postgres://prod"
            and lob.get("port") == "8080"
        )

        write_layers(
            tmp,
            strict_a={"server": {"port": 8080}},
            strict_b={"server": {"port": "eighty"}},
        )
        strict = run(script, tmp, "--strict", "strict_a.json", "strict_b.json")
        checks["strict_conflict_contract"] = (
            strict.returncode == 4
            and strict.stderr.strip() == "error: type conflict at server.port: number vs string"
            and strict.stdout == ""
        )

        write_layers(tmp, bool_a={"retries": 3}, bool_b={"retries": True})
        boolc = run(script, tmp, "--strict", "bool_a.json", "bool_b.json")
        checks["strict_bool_not_number"] = (
            boolc.returncode == 4
            and boolc.stderr.strip() == "error: type conflict at retries: number vs boolean"
        )

        write_layers(
            tmp,
            del_a={"keep": 1, "cache": {"size": 10}},
            del_b={"cache": "$delete"},
        )
        delc = run(script, tmp, "--strict", "del_a.json", "del_b.json")
        try:
            dob = json.loads(delc.stdout)
        except (json.JSONDecodeError, ValueError):
            dob = {}
        checks["strict_delete_exempt"] = (
            delc.returncode == 0 and dob == {"keep": 1}
        )

        write_layers(tmp, bad="{not json", arr="[1, 2]")
        missing = run(script, tmp, "base.json", "missing-layer.json", "bad.json")
        checks["missing_file_contract"] = (
            missing.returncode == 2
            and missing.stderr.strip() == "error: cannot read missing-layer.json"
            and missing.stdout == ""
        )

        badj = run(script, tmp, "base.json", "bad.json")
        checks["invalid_json_contract"] = (
            badj.returncode == 3
            and badj.stderr.strip() == "error: invalid JSON in bad.json"
            and badj.stdout == ""
        )

        arrj = run(script, tmp, "arr.json", "base.json")
        checks["toplevel_not_object_contract"] = (
            arrj.returncode == 5
            and arrj.stderr.strip() == "error: top-level value in arr.json must be an object"
            and arrj.stdout == ""
        )

        ver = run(script, tmp, "--version")
        checks["version_string"] = ver.returncode == 0 and ver.stdout.strip() == "cfgmerge 2.1.0"

        api_layers = [{"a": {"x": 1}, "b": 1}, {"a": {"y": 2}, "b": "$delete"}]
        write_layers(tmp, api_a=api_layers[0], api_b=api_layers[1])
        probe = (
            "import sys, io, json, contextlib\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "buf = io.StringIO()\n"
            "with contextlib.redirect_stdout(buf):\n"
            "    import cfgmerge\n"
            "assert buf.getvalue() == '', 'import printed output'\n"
            "layers = json.loads(sys.argv[2])\n"
            "print(json.dumps(cfgmerge.merge_configs(layers), sort_keys=True))\n"
        )
        try:
            imp = subprocess.run(
                [sys.executable, "-c", probe, str(ws), json.dumps(api_layers)],
                capture_output=True, text=True, timeout=30,
            )
            checks["importable_no_side_effects"] = imp.returncode == 0
            cli = run(script, tmp, "api_a.json", "api_b.json")
            try:
                api_obj = json.loads(imp.stdout)
                cli_obj = json.loads(cli.stdout)
            except (json.JSONDecodeError, ValueError):
                api_obj, cli_obj = 0, 1
            checks["merge_configs_matches_cli"] = (
                imp.returncode == 0
                and cli.returncode == 0
                and api_obj == cli_obj == {"a": {"x": 1, "y": 2}}
            )
        except subprocess.TimeoutExpired:
            checks["importable_no_side_effects"] = False
            checks["merge_configs_matches_cli"] = False


if __name__ == "__main__":
    main()
